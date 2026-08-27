import { describe, expect, it } from 'vitest'
import { formatCount } from './format'

describe('formatCount', () => {
  it('formats a count with Chinese locale separators', () => {
    expect(formatCount(129577)).toBe('129,577')
  })

  it('uses a dash for missing values', () => {
    expect(formatCount(null)).toBe('—')
  })
})
