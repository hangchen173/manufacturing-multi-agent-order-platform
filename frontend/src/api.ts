import type { OrderDetail, OrderSummary } from './types'

type ApiResponse<T> = { success: boolean; data?: T; message?: string }

export class ApiError extends Error {
  constructor(message: string, public orderId?: string) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  let payload: ApiResponse<T>
  try { payload = await response.json() as ApiResponse<T> }
  catch { throw new ApiError(`服务响应异常（${response.status}），请刷新订单列表核对处理状态`) }
  if (!response.ok || !payload.success) {
    const detail = payload.data as { message?: string; order_id?: string } | undefined
    throw new ApiError(payload.message || detail?.message || '请求失败，请稍后重试', detail?.order_id)
  }
  return payload.data as T
}

export const api = {
  listOrders: () => request<OrderSummary[]>('/orders'),
  getOrder: (id: string) => request<OrderDetail>(`/orders/${id}`),
  submitText: (orderText: string) => request<{ order_id: string }>('/upload_text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_text: orderText }) }),
  submitFile: (file: File) => { const form = new FormData(); form.append('file', file); return request<{ order_id: string }>('/upload', { method: 'POST', body: form }) },
  confirm: (id: string, action: 'confirm' | 'reject') => request<{ order_id: string }>(`/confirm/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }),
}
