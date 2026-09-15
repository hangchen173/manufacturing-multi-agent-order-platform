import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('API error details', () => {
  it('keeps the server failure reason and order id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({ success: false, data: { message: '模型超时', order_id: 'failed-order' } }) }))
    const error = await api.submitText('订单').catch(error => error)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.message).toBe('模型超时')
    expect(error.orderId).toBe('failed-order')
  })

  it('explains a proxy timeout without exposing a JSON parser error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 504, json: async () => { throw new SyntaxError('HTML response') } }))
    await expect(api.listOrders()).rejects.toThrow('服务响应异常（504）')
  })
})
