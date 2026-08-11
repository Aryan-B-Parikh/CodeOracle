import { describe, expect, it } from 'vitest'

import { formatPercent } from './format'

describe('formatPercent', () => {
  it('formats a percentage with one decimal', () => {
    expect(formatPercent(74.6)).toBe('74.6%')
  })

  it('supports custom precision', () => {
    expect(formatPercent(68.18, 2)).toBe('68.18%')
  })
})
