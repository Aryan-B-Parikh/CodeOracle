export interface UncoveredLineItem {
  file: string
  line: number
  branch: boolean
}

export interface FailedTestItem {
  name: string
  targetEntity?: string
  message: string
}

export interface TestRunData {
  testRunId: string
  status: string
  iteration: number
  testsGenerated: number
  testsPassed: number
  testsFailed: number
  lineCoverage: number
  branchCoverage: number
  target: number
  targetReached: boolean
  statusLabel: string
  uncoveredLines: UncoveredLineItem[]
  failedTests: FailedTestItem[]
  testCode?: string | null
  createdAt: string
}

export interface TestRunEnvelope {
  data: TestRunData
  error: string | null
}
