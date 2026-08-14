import { describe, it, expect } from 'vitest'
import { DependencyGraphTab } from './DependencyGraphTab'

describe('DependencyGraphTab Component', () => {
  it('is defined and exports React component', () => {
    expect(DependencyGraphTab).toBeDefined()
    expect(typeof DependencyGraphTab).toBe('function')
  })
})
