export interface BreakingChangeItem {
  entity: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW'
  reason: string
  affectedCallers: string[]
}

export interface SafetyScoreData {
  proposalId: string
  total: number
  apiCompatibility: number
  testCompatibility: number
  dependencyImpact: number
  behavioralRisk: number
  riskLevel: 'low' | 'medium' | 'high'
  breakingChanges: BreakingChangeItem[]
  recommendations: string[]
}

export interface SafetyScoreEnvelope {
  data: SafetyScoreData | null
  error: { code: string; message: string } | null
}
