export interface BreakingChangeItem {
  entity: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW'
  reason: string
  affectedCallers: string[]
}

export interface SafetyScoreData {
  proposalId: string
  testRunId?: string | null
  originalChecksum?: string
  proposedChecksum?: string
  total: number
  confidenceScore?: number
  confidenceLevel?: 'high' | 'medium' | 'low'
  apiCompatibility: number
  testCompatibility: number
  dependencyImpact: number
  behavioralRisk: number
  riskLevel: 'low' | 'medium' | 'high'
  behaviorStatus?: 'BEHAVIOR_PRESERVED' | 'BEHAVIOR_MUTATED' | 'UNVERIFIED'
  breakingChanges: BreakingChangeItem[]
  recommendations: string[]
}

export interface SafetyScoreEnvelope {
  data: SafetyScoreData | null
  error: { code: string; message: string } | null
}
