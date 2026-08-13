import { describe, it, expect } from 'vitest'
import { PipelineStatusCard } from './PipelineStatusCard'

describe('PipelineStatusCard Component (T-20)', () => {
  it('is defined and exports React component', () => {
    expect(PipelineStatusCard).toBeDefined()
  })

  it('renders pipeline stages without crashing', () => {
    const component = PipelineStatusCard({
      analysisStatus: 'running',
      currentStage: 'stage_1_scan',
    })
    expect(component).toBeDefined()
  })
})
