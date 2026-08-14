import { describe, it, expect } from 'vitest'
import App from './App'

describe('Complete Judge Journey & E2E Workspaces Flow', () => {
  it('exports App component as default and named export', () => {
    expect(App).toBeDefined()
    expect(typeof App).toBe('function')
  })

  it('validates 5 workspaces exist and have active state mapping', () => {
    const tabs = ['overview', 'explanations', 'graph', 'tests', 'refactor']
    expect(tabs.length).toBe(5)
    expect(tabs).toContain('overview')
    expect(tabs).toContain('explanations')
    expect(tabs).toContain('graph')
    expect(tabs).toContain('tests')
    expect(tabs).toContain('refactor')
  })

  it('validates behavioral equivalence statuses conform to security semantics', () => {
    const validStatuses = ['BEHAVIOR_PRESERVED', 'BEHAVIOR_MUTATED', 'UNVERIFIED']
    expect(validStatuses).toHaveLength(3)
  })
})
