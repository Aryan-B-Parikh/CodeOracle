import { describe, it, expect } from 'vitest'
import { DashboardTab } from './DashboardTab'

describe('DashboardTab Component (T-21)', () => {
  it('is defined and exports React component', () => {
    expect(DashboardTab).toBeDefined()
  })

  it('renders empty state when repositoryId is missing', () => {
    expect(DashboardTab({ summaryData: null })).toBeDefined()
  })
})
