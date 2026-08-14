import { describe, it, expect } from 'vitest'
import { SystemDocsTab } from './SystemDocsTab'

describe('SystemDocsTab Component', () => {
  it('is defined and exports React component', () => {
    expect(SystemDocsTab).toBeDefined()
    expect(typeof SystemDocsTab).toBe('function')
  })
})
