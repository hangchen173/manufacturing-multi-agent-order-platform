import { memo } from 'react'
import { formatAmount, formatPercent } from '../lib/format'

interface MetricsRowProps {
  customer: string
  amount: number | null | undefined
  confidence: number | null | undefined
}

/** 关键指标条。用 dl/dt/dd 表达"标签—取值"语义，比 div+span 更利于读屏。 */
export const MetricsRow = memo(function MetricsRow({ customer, amount, confidence }: MetricsRowProps) {
  return (
    <dl className="metrics">
      <div className="metrics__item">
        <dt>客户名称</dt>
        <dd>{customer || '—'}</dd>
      </div>
      <div className="metrics__item">
        <dt>总金额</dt>
        <dd className="num">{formatAmount(amount)}</dd>
      </div>
      <div className="metrics__item">
        <dt>整体置信度</dt>
        <dd className="num">{formatPercent(confidence)}</dd>
      </div>
    </dl>
  )
})
