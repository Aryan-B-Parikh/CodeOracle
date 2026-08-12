export interface RefactorProposal {
  proposalId: string
  entityId: string
  entityName: string
  filePath: string
  original: string
  proposed: string
  rationale: string[]
  behavioralDifferences: string[]
  originalChecksum: string
}

export interface RefactorProposalEnvelope {
  data: RefactorProposal | null
  error: { code: string; message: string } | null
}
