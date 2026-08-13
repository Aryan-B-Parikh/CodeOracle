import { TestRunEnvelope } from '../types/test_run'
import { RefactorProposalEnvelope } from '../types/refactor'

const API_BASE = '/api/v1'

export interface RepositorySummary {
  id: string
  name: string
  status: string
  loc: number
  entityCount: number
  languages: Record<string, boolean>
}

export interface RepositoryListEnvelope {
  data: RepositorySummary[]
}

export async function fetchRepositories(): Promise<RepositoryListEnvelope> {
  const res = await fetch(`${API_BASE}/repositories`)
  if (!res.ok) {
    throw new Error(`Failed to list repositories: status ${res.status}`)
  }
  return res.json()
}

export async function uploadRepository(file: File): Promise<RepositorySummary> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/repositories/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    throw new Error(`Upload failed: status ${res.status}`)
  }
  const envelope = await res.json()
  return envelope.data as RepositorySummary
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

