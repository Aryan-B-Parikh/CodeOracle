import { describe, it, expect } from 'vitest'
import { ExplanationTab } from './ExplanationTab'

describe('ExplanationTab Component', () => {
  it('is defined and exports React component', () => {
    expect(ExplanationTab).toBeDefined()
    expect(typeof ExplanationTab).toBe('function')
  })
})
