import { TestRunEnvelope } from '../types/test_run'

const API_BASE = '/api/v1'

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
