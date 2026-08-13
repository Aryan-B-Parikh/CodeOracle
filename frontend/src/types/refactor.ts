export interface BreakingChange {
  entity: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW'
  reason: string
  affectedCallers: string[]
}

export interface BreakingChangesResult {
  detected: boolean
  changes: BreakingChange[]
}

export interface RefactorProposal {
  proposalId: string
  entityId: string
  entityName: string
  filePath: string
  original: string
  proposed: string
  rationale: string[]
  behavioralDifferences: string[]
  breakingChanges?: BreakingChangesResult
  originalChecksum: string
}

export interface RefactorProposalEnvelope {
  data: RefactorProposal | null
  error: { code: string; message: string } | null
}
