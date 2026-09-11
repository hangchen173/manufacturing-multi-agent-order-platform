import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

  it('switches from PDF to XLSX without leaving the old result visible', async () => {
    let finishUpload!: (value: { order_id: string }) => void
    const pdf = new File(['pdf'], 'first.pdf', { type: 'application/pdf' })
    const xlsx = new File(['xlsx'], 'second.xlsx')
    const excelDetail = { ...detail, order_id: 'excel-order', document_path: 'uploads/second.xlsx',
      final_result: { ...detail.final_result, parsed_order: { ...detail.final_result.parsed_order, order_number: 'EXCEL-2' } } }
    api.getOrder.mockImplementation(async id => id === 'excel-order' ? excelDetail : detail)
    api.submitFile.mockResolvedValueOnce({ order_id: 'order-1' }).mockImplementationOnce(
      () => new Promise(resolve => { finishUpload = resolve })
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: '上传文件' }))
    fireEvent.change(screen.getByLabelText('订单文件'), { target: { files: [pdf] } })
    fireEvent.click(screen.getByRole('button', { name: '开始解析' }))
    expect(await screen.findByRole('heading', { name: 'ORD-1' })).toBeTruthy()
    await waitFor(() => expect((screen.getByLabelText('订单文件') as HTMLInputElement).disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('订单文件'), { target: { files: [xlsx] } })
    expect(screen.queryByRole('heading', { name: 'ORD-1' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '开始解析' }))
    expect(screen.getByRole('status').textContent).toContain('second.xlsx')
    expect((screen.getByLabelText('订单文件') as HTMLInputElement).disabled).toBe(true)
    expect(api.submitFile.mock.calls.map(([file]) => file)).toEqual([pdf, xlsx])
    await act(async () => finishUpload({ order_id: 'excel-order' }))
    expect(await screen.findByRole('heading', { name: 'EXCEL-2' })).toBeTruthy()
    expect(screen.getByText('源文件：second.xlsx')).toBeTruthy()
  })

  it('ignores an old history response after choosing another file', async () => {
    let finishDetail!: (value: typeof detail) => void
    api.getOrder.mockImplementationOnce(() => new Promise(resolve => { finishDetail = resolve }))
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /order-1/i }))
    fireEvent.click(screen.getByRole('button', { name: '上传文件' }))
    fireEvent.change(screen.getByLabelText('订单文件'), { target: { files: [new File(['xlsx'], 'new.xlsx')] } })
    await act(async () => finishDetail(detail))
    expect(screen.queryByRole('heading', { name: 'ORD-1' })).toBeNull()
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

  it('shows order level risks, unknown fields and rejected candidates', async () => {
    api.getOrder.mockResolvedValue({ ...detail, final_result: { ...detail.final_result,
      matched_order: { items: [{ material_name: '接触器', specification: null, quantity: null, unit_price: null, match_score: 0.99, candidate_skus: ['CNT-001', 'CNT-002'], rejection_reason: '关键后缀未提供' }] },
      risk_result: { needs_confirmation: true, overall_confidence: .5, issues: [{ item_index: -1, issue_type: 'line_total', severity: 'high', description: '金额不一致' }] },
      business_decision: { action: 'manual_review', reason: '规格有歧义', normalizations: [] },
    } })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /order-1/i }))
    expect(await screen.findByText('整单：金额不一致', { exact: false })).toBeTruthy()
    expect(screen.queryByText(/第 0 项/)).toBeNull()
    expect(screen.getByText('CNT-001、CNT-002')).toBeTruthy()
    expect(screen.getAllByText('未提供').length).toBe(3)
    expect(screen.getByText('系统判定：人工审核')).toBeTruthy()
  })

  it('shows which row and field were normalized', async () => {
    api.getOrder.mockResolvedValue({ ...detail, final_result: { ...detail.final_result,
      business_decision: { action: 'auto_correct', reason: '登记别名', normalizations: [{ item_index: 1, field: 'material_name', original_value: '螺丝', standard_value: '标准螺钉', basis: '登记别名匹配' }] },
    } })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /order-1/i }))
    expect(await screen.findByText(/第 2 项 · 物料名称：螺丝 → 标准螺钉/)).toBeTruthy()
  })
})
