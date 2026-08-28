import { afterEach, describe, expect, it, vi } from 'vitest'

import { http } from './http'
import { getReimbursements } from './reimbursement'

describe('getReimbursements', () => {
  afterEach(() => vi.restoreAllMocks())

  it('does not send blank date filters that FastAPI rejects', async () => {
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: { records: [] } })

    await getReimbursements({
      view: 'all',
      team: '',
      keyword: '',
      start_date: '',
      end_date: '',
    })

    expect(get).toHaveBeenCalledWith('/reimbursements', {
      params: { view: 'all' },
    })
  })
})
