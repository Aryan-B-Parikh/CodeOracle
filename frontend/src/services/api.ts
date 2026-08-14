import { TestRunEnvelope } from '../types/test_run'
import { RefactorProposalEnvelope } from '../types/refactor'
import { SafetyScoreEnvelope } from '../types/safety'

const API_BASE = '/api/v1'

export interface RepositorySummary {
  id: string
  name: string
  status: string
  sourceType?: string
  githubUrl?: string | null
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

export async function importRepository(githubUrl: string): Promise<RepositorySummary> {
  const res = await fetch(`${API_BASE}/repositories/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })
  if (!res.ok) {
    throw new Error(`Import failed: status ${res.status}`)
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



