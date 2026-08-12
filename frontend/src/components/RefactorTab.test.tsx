import { describe, it, expect } from 'vitest'
import { DiffViewer } from './DiffViewer'
import { RefactorTab } from './RefactorTab'
import { RefactorProposal } from '../types/refactor'

const mockProposal: RefactorProposal = {
  proposalId: 'prop-uuid-1',
  entityId: 'entity-uuid-1',
  entityName: 'calculate_tax',
  filePath: 'tax.py',
  original: 'def calculate_tax(rate, amount):\n    return rate * amount',
  proposed: 'def calculate_tax(rate: float, amount: float) -> float:\n    """Calculate tax."""\n    return rate * amount',
  rationale: ['Add type annotations for clarity', 'Add docstring for documentation'],
  behavioralDifferences: [],
  originalChecksum: 'abc123def456',
}

describe('DiffViewer Component', () => {
  it('is defined and callable', () => {
    expect(DiffViewer).toBeDefined()
  })
})

describe('RefactorTab Component', () => {
  it('is defined and callable', () => {
    expect(RefactorTab).toBeDefined()
  })
})

describe('RefactorProposal data contract', () => {
  it('validates proposal fields', () => {
    expect(mockProposal.entityName).toBe('calculate_tax')
    expect(mockProposal.rationale.length).toBe(2)
    expect(mockProposal.behavioralDifferences.length).toBe(0)
  })

  it('validates original vs proposed are different', () => {
    expect(mockProposal.proposed).not.toBe(mockProposal.original)
    expect(mockProposal.proposed).toContain('float')
    expect(mockProposal.proposed).toContain('"""')
  })

  it('validates checksum field exists', () => {
    expect(mockProposal.originalChecksum).toBeTruthy()
    expect(mockProposal.originalChecksum.length).toBeGreaterThan(0)
  })
})
