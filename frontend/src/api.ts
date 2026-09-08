import type { OrderDetail, OrderSummary } from './types'

type ApiResponse<T> = { success: boolean; data?: T; message?: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  const payload = await response.json() as ApiResponse<T>
  if (!response.ok || !payload.success) throw new Error(payload.message || '请求失败，请稍后重试')
  return payload.data as T
}

export const api = {
  listOrders: () => request<OrderSummary[]>('/orders'),
  getOrder: (id: string) => request<OrderDetail>(`/orders/${id}`),
  submitText: (orderText: string) => request<{ order_id: string }>('/upload_text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_text: orderText }) }),
  submitFile: (file: File) => { const form = new FormData(); form.append('file', file); return request<{ order_id: string }>('/upload', { method: 'POST', body: form }) },
  confirm: (id: string, action: 'confirm' | 'reject') => request<{ order_id: string }>(`/confirm/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }),
}
