import { describe, it, expect } from 'vitest'
import { SafetyScoreCard } from './SafetyScoreCard'
import { SafetyScoreData } from '../types/safety'

const mockSafetyData: SafetyScoreData = {
  proposalId: 'prop-uuid-123',
  total: 88,
  apiCompatibility: 100,
  testCompatibility: 80,
  dependencyImpact: 85,
  behavioralRisk: 85,
  riskLevel: 'low',
  breakingChanges: [],
  recommendations: ['Refactor proposal carries low risk; behavior is well-preserved.'],
}

describe('SafetyScoreCard Component (T-19 & T-18)', () => {
  it('is defined and exports React component', () => {
    expect(SafetyScoreCard).toBeDefined()
  })

  it('validates mock safety data structure', () => {
    expect(mockSafetyData.total).toBe(88)
    expect(mockSafetyData.riskLevel).toBe('low')
    expect(mockSafetyData.apiCompatibility).toBe(100)
    expect(mockSafetyData.recommendations.length).toBe(1)
  })
})
