import { memo } from 'react'
import { Check, ShieldAlert, X } from 'lucide-react'
import { fileNameFromPath, formatDateTime } from '../lib/format'
import { decisionLabels, normalizationFieldLabel, statusLabels } from '../lib/labels'
import type { MatchedOrderItem, NormalizationChange, OrderDetail, RiskIssue, Transition } from '../types'
import { MaterialTable } from './MaterialTable'
import { MetricsRow } from './MetricsRow'
import { RiskIssues } from './RiskIssues'
import { StatusBadge } from './StatusBadge'

type ReviewActions = NonNullable<OrderDetail['review_actions']>

// 模块级常量：缺省值复用同一个数组引用，避免每次渲染都新建空数组
// 从而让子组件的 memo 失效。
const NO_ITEMS: MatchedOrderItem[] = []
const NO_ISSUES: RiskIssue[] = []
const NO_NORMALIZATIONS: NormalizationChange[] = []
const NO_REVIEWS: ReviewActions = []
const NO_TRANSITIONS: Transition[] = []

interface ResultPanelProps {
  order: OrderDetail
  busy: boolean
  onConfirm: (action: 'confirm' | 'reject') => void
}

/**
 * 订单结果面板。
 *
 * 这是整棵树里最重的一块（长表格 + 多个记录区块），memo 边界放在这里意味着：
 * 输入文本、切换输入方式、列表刷新都不会让它重新渲染，
 * 只有订单数据本身或忙碌态变化时才会重算。
 */
export const ResultPanel = memo(function ResultPanel({ order, busy, onConfirm }: ResultPanelProps) {
  const result = order.final_result
  const parsed = result?.parsed_order
  const items = result?.matched_order?.items ?? NO_ITEMS
  const issues = result?.risk_result?.issues ?? NO_ISSUES
  const decision = result?.business_decision
  const normalizations = decision?.normalizations ?? NO_NORMALIZATIONS
  const reviews = order.review_actions ?? NO_REVIEWS
  const transitions = order.transition_history ?? NO_TRANSITIONS
  const request = order.confirmation_requests.at(-1)

  return (
    <section className="panel panel--result">
      <div className="section-heading">
        <div>
          <p className="eyebrow">订单详情</p>
          <h2 className="order-title">{parsed?.order_number || order.order_id}</h2>
        </div>
        <StatusBadge status={order.status} />
      </div>

      {order.document_path && <p className="meta-line">源文件：{fileNameFromPath(order.document_path)}</p>}

      {order.error_message && (
        <div className="alert alert--error" role="alert">
          <ShieldAlert size={18} aria-hidden="true" />
          <span>{order.error_message}</span>
        </div>
      )}

      {order.status === 'needs_confirmation' && (
        <div className="confirmation">
          <div>
            <h3>需要人工确认</h3>
            {request?.needs_confirmation_reasons?.map(reason => <p key={reason}>{reason}</p>)}
          </div>
          <div className="confirmation__actions">
            <button type="button" className="button button--approve" disabled={busy} onClick={() => onConfirm('confirm')}>
              <Check size={16} aria-hidden="true" />
              确认通过
            </button>
            <button type="button" className="button button--reject" disabled={busy} onClick={() => onConfirm('reject')}>
              <X size={16} aria-hidden="true" />
              拒绝订单
            </button>
          </div>
        </div>
      )}

      {decision && (
        <div className="decision">
          <h3>系统判定：{decisionLabels[decision.action]}</h3>
          <p>{decision.reason}</p>
        </div>
      )}

      <RiskIssues issues={issues} />

      <MetricsRow
        customer={parsed?.customer_name ?? ''}
        amount={parsed?.total_amount}
        confidence={result?.risk_result?.overall_confidence}
      />

      <section className="result-section result-section--table">
        <h3>物料匹配结果</h3>
        <MaterialTable items={items} />
      </section>

      {normalizations.length > 0 && (
        <div className="result-section defer-paint">
          <h3>归一化记录</h3>
          {normalizations.map((change, index) => (
            <p className="record" key={index}>
              第 {change.item_index + 1} 项 · {normalizationFieldLabel(change.field)}：{change.original_value} → {change.standard_value}
              <small>{change.basis}</small>
            </p>
          ))}
        </div>
      )}

      {reviews.length > 0 && (
        <div className="result-section defer-paint">
          <h3>人工审核记录</h3>
          {reviews.map((review, index) => (
            <p className="record" key={index}>
              {formatDateTime(review.timestamp)} · {review.action === 'confirm' ? '确认通过' : '拒绝订单'}
              {review.comment ? ` · ${review.comment}` : ''}
            </p>
          ))}
        </div>
      )}

      <details className="transitions defer-paint">
        <summary>状态流转（{transitions.length}）</summary>
        {transitions.map((item, index) => (
          <p key={index}>
            {formatDateTime(item.timestamp)} · {statusLabels[item.to_status]}
            {item.reason ? ` · ${item.reason}` : ''}
          </p>
        ))}
      </details>
    </section>
  )
})
