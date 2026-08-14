import { TestRunEnvelope } from '../types/test_run'
import { RefactorProposalEnvelope } from '../types/refactor'
import { SafetyScoreEnvelope } from '../types/safety'

const API_BASE = '/api/v1'

// Latest-request-wins guards prevent slow responses from an older user action
// from overwriting the result of a newer action. Requests are allowed to finish
// normally; stale callers simply receive the newest request's result instead.
let latestEntityExplanationRequest: Promise<ExplanationEnvelope> | null = null
let latestEntityImpactRequest: Promise<ImpactEnvelope> | null = null
let latestEntitySourceRequest: Promise<{ file: string; lineStart: number; lineEnd: number; code: string }> | null = null
let latestRepositoryGraphRequest: Promise<GraphEnvelope> | null = null
let latestRepositoryEntitiesRequest: Promise<EntityItem[]> | null = null

export interface RepositorySummary {
  id: string
  name: string
  status: string
  sourceType?: string
  githubUrl?: string | null
  loc: number
  entityCount: number
  fileCount?: number
  languages: Record<string, boolean>
  warnings?: string[]
  createdAt?: string
  updatedAt?: string
}

export interface RepositoryListEnvelope {
  data: RepositorySummary[]
}

export interface EntityItem {
  id: string
  name: string
  type: string
  file: string
  lineStart: number
  lineEnd: number
  signature?: string | null
  language?: string
  complexity: number
  isPublic?: boolean
  docstring?: string | null
}

export interface EvidenceCitation {
  claim: string
  file: string
  lineStart: number
  lineEnd: number
  code: string
}

export interface ExplanationFields {
  purpose: string
  inputs: string
  outputs: string
  sideEffects: string
  dependencies: string
  controlFlow: string
  errorHandling: string
  businessRules: string
  complexity: number
  risks: string
}

export interface ExplanationData {
  entity: {
    id?: string
    name: string
    type: string
    file: string
    lineStart: number
    lineEnd: number
  }
  explanation: ExplanationFields
  evidence: EvidenceCitation[]
  provider?: string | null
}

export interface ExplanationEnvelope {
  data: ExplanationData | null
  error?: { code: string; message: string } | null
}

export interface CallerItem {
  caller: string
  file: string
  lineStart: number
  lineEnd: number
  callLine: number
}

export interface CalleeItem {
  callee: string
  file: string
  lineStart: number
  lineEnd: number
}

export interface ImpactData {
  entity: {
    name: string
    file: string
    lineStart: number
    lineEnd: number
  }
  callers: CallerItem[]
  callees: CalleeItem[]
  impact: 'high' | 'medium' | 'low' | string
  impactReason: string
}

export interface ImpactEnvelope {
  data: ImpactData | null
  error?: { code: string; message: string } | null
}

export interface GraphNode {
  id: string
  label: string
  type: string
  complexity: number
  file?: string | null
  lineStart?: number | null
  lineEnd?: number | null
  qualifiedName?: string | null
  riskScore?: number | null
}

export interface GraphEdge {
  source: string
  target: string
  kind: 'call' | 'import' | 'contains' | string
}

export interface GraphMeta {
  circularDependencies: { cycle: string[] }[]
  highRiskNodeIds: string[]
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
  meta: GraphMeta
}

export interface GraphEnvelope {
  data: GraphPayload
  error?: { code: string; message: string } | null
}

export async function fetchRepositories(): Promise<RepositoryListEnvelope> {
  const res = await fetch(`${API_BASE}/repositories`)
  if (!res.ok) {
    throw new Error(`Failed to list repositories: status ${res.status}`)
  }
  return res.json()
}

export async function importRepository(githubUrl: string): Promise<RepositorySummary> {
  const res = await fetch(`${API_BASE}/repositories/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.detail || `Import failed: status ${res.status}`)
  }
  const envelope = await res.json()
  return envelope.data as RepositorySummary
}

export async function triggerAnalysis(repositoryId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}/analyze`, {
    method: 'POST',
  })
  if (!res.ok && res.status !== 409) {
    throw new Error(`Failed to start analysis: status ${res.status}`)
  }
}

export async function uploadRepository(file: File): Promise<RepositorySummary> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/repositories/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.detail || `Upload failed: status ${res.status}`)
  }
  const envelope = await res.json()
  return envelope.data as RepositorySummary
}

export async function deleteRepository(repositoryId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    throw new Error(`Failed to delete repository: status ${res.status}`)
  }
}

export async function fetchRepositoryEntities(repositoryId: string): Promise<EntityItem[]> {
  const request = (async () => {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/entities`)
    if (!res.ok) {
      throw new Error(`Failed to list entities: status ${res.status}`)
    }
    const envelope = await res.json()
    return (envelope.data || []) as EntityItem[]
  })()

  latestRepositoryEntitiesRequest = request
  const result = await request
  return request === latestRepositoryEntitiesRequest ? result : latestRepositoryEntitiesRequest!
}

export async function fetchEntityExplanation(
  repositoryId: string,
  entityId: string
): Promise<ExplanationEnvelope> {
  const request = (async () => {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/entities/${entityId}/explanation`)
    if (!res.ok) {
      throw new Error(`Failed to fetch explanation: status ${res.status}`)
    }
    return res.json() as Promise<ExplanationEnvelope>
  })()

  latestEntityExplanationRequest = request
  const result = await request
  return request === latestEntityExplanationRequest ? result : latestEntityExplanationRequest!
}

export async function fetchEntityImpact(
  repositoryId: string,
  entityId: string
): Promise<ImpactEnvelope> {
  const request = (async () => {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/entities/${entityId}/impact`)
    if (!res.ok) {
      throw new Error(`Failed to fetch impact: status ${res.status}`)
    }
    return res.json() as Promise<ImpactEnvelope>
  })()

  latestEntityImpactRequest = request
  const result = await request
  return request === latestEntityImpactRequest ? result : latestEntityImpactRequest!
}

export async function fetchEntitySource(
  repositoryId: string,
  entityId: string
): Promise<{ file: string; lineStart: number; lineEnd: number; code: string }> {
  const request = (async () => {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/entities/${entityId}/source`)
    if (!res.ok) {
      throw new Error(`Failed to fetch source: status ${res.status}`)
    }
    const envelope = await res.json()
    return envelope.data as { file: string; lineStart: number; lineEnd: number; code: string }
  })()

  latestEntitySourceRequest = request
  const result = await request
  return request === latestEntitySourceRequest ? result : latestEntitySourceRequest!
}

export async function fetchRepositoryGraph(repositoryId: string): Promise<GraphEnvelope> {
  const request = (async () => {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/graph`)
    if (!res.ok) {
      throw new Error(`Failed to fetch graph: status ${res.status}`)
    }
    return res.json() as Promise<GraphEnvelope>
  })()

  latestRepositoryGraphRequest = request
  const result = await request
  return request === latestRepositoryGraphRequest ? result : latestRepositoryGraphRequest!
}

export async function fetchLatestTestRun(repositoryId: string): Promise<TestRunEnvelope> {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}/tests/latest`)
  if (!res.ok) {
    throw new Error(`Failed to fetch latest test run: status ${res.status}`)
  }
  return res.json()
}

export async function triggerGenerateUncovered(
  repositoryId: string,
  maxIterations = 3,
  targetCoverage = 60.0
): Promise<TestRunEnvelope> {
  const url = `${API_BASE}/repositories/${repositoryId}/tests/generate-uncovered?max_iterations=${maxIterations}&target_coverage=${targetCoverage}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to generate uncovered tests: status ${res.status}`)
  }
  return res.json()
}

export async function proposeRefactor(
  repositoryId: string,
  entityId: string
): Promise<RefactorProposalEnvelope> {
  const url = `${API_BASE}/repositories/${repositoryId}/refactors/${entityId}/propose`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to propose refactor: status ${res.status}`)
  }
  return res.json()
}

export async function fetchSafetyScore(
  repositoryId: string,
  proposalId: string
): Promise<SafetyScoreEnvelope> {
  const url = `${API_BASE}/repositories/${repositoryId}/refactors/${proposalId}/safety`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to fetch safety score: status ${res.status}`)
  }
  return res.json()
}

export async function fetchRepositorySummary(repositoryId: string) {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}/summary`)
  if (!res.ok) {
    throw new Error(`Failed to fetch repository summary: status ${res.status}`)
  }
  return res.json()
}

export async function fetchRepositoryStatus(repositoryId: string) {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}/status`)
  if (!res.ok) {
    throw new Error(`Failed to fetch repository status: status ${res.status}`)
  }
  return res.json()
}

export async function downloadExecutiveReport(repositoryId: string, repositoryName = 'Repository') {
  const res = await fetch(`${API_BASE}/repositories/${repositoryId}/report`)
  if (!res.ok) {
    throw new Error(`Failed to download report: status ${res.status}`)
  }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${repositoryName.replace(/\s+/g, '_')}_Executive_Report.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
