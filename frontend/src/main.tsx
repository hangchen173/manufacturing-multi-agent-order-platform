import { useEffect, useRef, useState } from 'react'
import { Check, ClipboardList, FileUp, History, LoaderCircle, Send, ShieldAlert, X } from 'lucide-react'
import { api } from './api'
import type { MatchedOrderItem, OrderDetail, OrderSummary } from './types'
import './styles.css'

const ACCEPTED_TYPES = '.txt,.csv,.pdf,.xlsx,.xls,.png,.jpg,.jpeg'
const sampleText = '订单编号: ORD-2026-001\n客户: XX制造公司\n物料: 不锈钢螺丝 M8x30, 数量: 1000, 单价: 0.5, 交期: 2026-09-30'
const labels: Record<string, string> = { pending: '待处理', parsing: '解析中', matching: '匹配中', risk_checking: '风控中', needs_confirmation: '待确认', completed: '已完成', failed: '失败' }

function scoreClass(score: number) { return score < .8 ? 'score low' : score < .9 ? 'score medium' : 'score high' }
function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) }

function ResultPanel({ order, onConfirm }: { order: OrderDetail; onConfirm: (action: 'confirm' | 'reject') => void }) {
  const result = order.final_result
  const matchedItems: MatchedOrderItem[] = result?.matched_order?.items ?? []
  const parsed = result?.parsed_order
  const issues = result?.risk_result?.issues ?? []
  const request = order.confirmation_requests.at(-1)
  return <section className="result-panel">
    <div className="section-heading"><div><p className="eyebrow">订单详情</p><h2>{parsed?.order_number || order.order_id}</h2></div><span className={`status ${order.status}`}>{labels[order.status]}</span></div>
    {order.error_message && <div className="alert error"><ShieldAlert size={18}/>{order.error_message}</div>}
    {order.status === 'needs_confirmation' && <div className="confirmation">
      <div><h3>需要人工确认</h3>{request?.needs_confirmation_reasons?.map(reason => <p key={reason}>{reason}</p>)}</div>
      <div className="action-buttons"><button className="button approve" onClick={() => onConfirm('confirm')}><Check size={16}/>确认通过</button><button className="button reject" onClick={() => onConfirm('reject')}><X size={16}/>拒绝订单</button></div>
    </div>}
    {issues.length > 0 && <div className="issues"><h3>风险问题</h3>{issues.map(issue => <p key={`${issue.item_index}-${issue.issue_type}`}><span className={`severity ${issue.severity}`}>{issue.severity}</span>第 {issue.item_index + 1} 项：{issue.description}</p>)}</div>}
    <div className="metrics"><div><span>客户名称</span><strong>{parsed?.customer_name || '-'}</strong></div><div><span>总金额</span><strong>{parsed?.total_amount == null ? '-' : `¥${parsed.total_amount.toFixed(2)}`}</strong></div><div><span>整体置信度</span><strong>{result?.risk_result ? `${Math.round(result.risk_result.overall_confidence * 100)}%` : '-'}</strong></div></div>
    <div className="table-wrap"><table><thead><tr><th>物料</th><th>规格</th><th>数量</th><th>单价</th><th>标准 SKU</th><th>匹配物料</th><th>匹配得分</th></tr></thead><tbody>{matchedItems.map((item, index) => <tr key={index}><td>{item.material_name}</td><td>{item.specification}</td><td>{item.quantity} {item.unit}</td><td>{item.unit_price ?? '-'}</td><td>{item.sku_code || '-'}</td><td>{item.matched_material_name || '-'}</td><td><span className={scoreClass(item.match_score)}>{item.match_score.toFixed(2)}</span></td></tr>)}</tbody></table>{matchedItems.length === 0 && <p className="empty">暂无可展示的物料匹配结果。</p>}</div>
    <details className="transitions"><summary>状态流转（{order.transition_history.length}）</summary>{order.transition_history.map((item, index) => <p key={index}>{formatDate(item.timestamp)} · {labels[item.to_status]} {item.reason ? `· ${item.reason}` : ''}</p>)}</details>
  </section>
}

function App() {
  const [mode, setMode] = useState<'text' | 'file'>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [selected, setSelected] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const refreshOrders = async () => { setHistoryLoading(true); try { setOrders(await api.listOrders()) } catch (e) { setError(e instanceof Error ? e.message : '无法加载历史订单') } finally { setHistoryLoading(false) } }
  useEffect(() => { void refreshOrders() }, [])
  const selectOrder = async (id: string) => { setError(''); try { setSelected(await api.getOrder(id)) } catch (e) { setError(e instanceof Error ? e.message : '无法加载订单详情') } }
  const submit = async () => {
    if (mode === 'text' && !text.trim()) { setError('请输入订单文本'); return }
    if (mode === 'file' && !file) { setError('请选择订单文件'); return }
    setLoading(true); setError('')
    try { const result = mode === 'text' ? await api.submitText(text) : await api.submitFile(file as File); await selectOrder(result.order_id); await refreshOrders() } catch (e) { setError(e instanceof Error ? e.message : '订单提交失败') } finally { setLoading(false) }
  }
  const confirm = async (action: 'confirm' | 'reject') => { if (!selected) return; setLoading(true); setError(''); try { await api.confirm(selected.order_id, action); await selectOrder(selected.order_id); await refreshOrders() } catch (e) { setError(e instanceof Error ? e.message : '操作失败') } finally { setLoading(false) } }

  return <main><header><div className="brand"><ClipboardList size={25}/><span>智能订单工作台</span></div><p>制造业多 Agent 订单解析与风险审核</p></header><div className="layout"><aside><section className="sidebar-section"><div className="sidebar-title"><History size={17}/><h2>历史订单</h2></div>{historyLoading ? <p className="muted">正在加载...</p> : orders.length === 0 ? <p className="muted">暂无历史订单</p> : <ul className="order-list">{orders.map(order => <li key={order.order_id}><button className={selected?.order_id === order.order_id ? 'selected' : ''} onClick={() => void selectOrder(order.order_id)}><span className={`status ${order.status}`}>{labels[order.status]}</span><strong>{order.order_id.slice(0, 8)}</strong><small>{formatDate(order.created_at)}</small></button></li>)}</ul>}</section></aside><div className="workspace"><section className="submission"><div className="section-heading"><div><p className="eyebrow">新订单</p><h1>提交待解析订单</h1></div></div><div className="segmented"><button className={mode === 'text' ? 'active' : ''} onClick={() => setMode('text')}>粘贴文本</button><button className={mode === 'file' ? 'active' : ''} onClick={() => setMode('file')}>上传文件</button></div>{mode === 'text' ? <textarea value={text} onChange={event => setText(event.target.value)} placeholder={sampleText} /> : <div className="file-drop" onClick={() => fileInput.current?.click()}><FileUp size={24}/><strong>{file ? file.name : '选择订单文件'}</strong><span>PDF、Excel、图片、TXT 或 CSV，最大 16 MB</span><input ref={fileInput} type="file" accept={ACCEPTED_TYPES} onChange={event => setFile(event.target.files?.[0] || null)} /></div>}{error && <div className="alert error"><ShieldAlert size={18}/>{error}</div>}<button className="button primary" disabled={loading} onClick={() => void submit()}>{loading ? <LoaderCircle className="spin" size={17}/> : <Send size={17}/>}开始解析</button></section>{selected ? <ResultPanel order={selected} onConfirm={action => void confirm(action)} /> : <section className="placeholder"><ClipboardList size={32}/><h2>等待订单处理</h2><p>提交新订单，或从左侧选择一条历史订单查看完整处理结果。</p></section>}</div></div></main>
}

export default App
