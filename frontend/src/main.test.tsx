import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './main'

const { api } = vi.hoisted(() => ({ api: {
  listOrders: vi.fn(),
  getOrder: vi.fn(),
  submitText: vi.fn(),
  submitFile: vi.fn(),
  confirm: vi.fn(),
} }))

vi.mock('./api', () => ({ api }))

const detail = {
  order_id: 'order-1', status: 'needs_confirmation' as const,
  created_at: '2026-08-24T10:00:00Z', updated_at: '2026-08-24T10:00:00Z',
  confirmation_count: 1, confirmation_requests: [{ needs_confirmation_reasons: ['发现 1 个风险问题'] }],
  transition_history: [], final_result: { status: 'needs_confirmation' as const, parsed_order: { order_number: 'ORD-1', customer_name: '测试客户', items: [], parsing_confidence: .9 }, matched_order: { items: [] }, risk_result: { needs_confirmation: true, issues: [], overall_confidence: .9 } },
}

describe('order console', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listOrders.mockResolvedValue([{ order_id: 'order-1', status: 'needs_confirmation', created_at: '2026-08-24T10:00:00Z', updated_at: '2026-08-24T10:00:00Z', confirmation_count: 1 }])
    api.getOrder.mockResolvedValue(detail)
    api.submitText.mockResolvedValue({ order_id: 'order-1' })
    api.submitFile.mockResolvedValue({ order_id: 'order-1' })
    api.confirm.mockResolvedValue({ order_id: 'order-1' })
  })

  it('submits pasted text and displays the returned order detail', async () => {
    render(<App />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '订单编号: ORD-1' } })
    fireEvent.click(screen.getByRole('button', { name: '开始解析' }))
    await waitFor(() => expect(api.submitText).toHaveBeenCalledWith('订单编号: ORD-1'))
    expect(await screen.findByText('需要人工确认')).toBeTruthy()
  })

  it('submits a selected file', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: '上传文件' }))
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['order'], 'order.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: '开始解析' }))
    await waitFor(() => expect(api.submitFile).toHaveBeenCalledWith(file))
  })

  it('loads a history detail and sends the confirmation action', async () => {
    render(<App />)
    await screen.findByText('order-1', { exact: false })
    fireEvent.click(screen.getByRole('button', { name: /order-1/i }))
    expect(await screen.findByText('确认通过')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '确认通过' }))
    await waitFor(() => expect(api.confirm).toHaveBeenCalledWith('order-1', 'confirm'))
  })

  it('shows API errors to the operator', async () => {
    api.submitText.mockRejectedValueOnce(new Error('服务不可用'))
    render(<App />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '订单' } })
    fireEvent.click(screen.getByRole('button', { name: '开始解析' }))
    expect(await screen.findByText('服务不可用')).toBeTruthy()
  })
})
