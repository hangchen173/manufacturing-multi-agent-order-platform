import { memo } from 'react'
import { History } from 'lucide-react'
import { formatDateTime, shortOrderId } from '../lib/format'
import type { OrderSummary } from '../types'
import { StatusBadge } from './StatusBadge'

const SKELETON_ROWS = [0, 1, 2, 3]

interface OrderListItemProps {
  order: OrderSummary
  selected: boolean
  busy: boolean
  onSelect: (orderId: string) => void
}

/**
 * 单个历史订单条目。memo 让"只有被点中的那条"因选中态变化而重渲染，
 * 列表其余条目保持不动；回调由父级稳定传入，不会因父组件重渲染而失效。
 */
const OrderListItem = memo(function OrderListItem({ order, selected, busy, onSelect }: OrderListItemProps) {
  return (
    <li>
      <button
        type="button"
        className={selected ? 'order-item order-item--selected' : 'order-item'}
        aria-current={selected ? 'true' : undefined}
        disabled={busy}
        onClick={() => onSelect(order.order_id)}
      >
        <StatusBadge status={order.status} />
        <strong className="order-item__id" title={order.order_id}>
          {shortOrderId(order.order_id)}
        </strong>
        <small className="order-item__time">{formatDateTime(order.created_at)}</small>
      </button>
    </li>
  )
})

interface OrderSidebarProps {
  orders: OrderSummary[]
  selectedId: string | null
  loading: boolean
  busy: boolean
  refreshing: boolean
  onSelect: (orderId: string) => void
}

/**
 * 历史订单侧栏。只订阅 orders / selectedId / loading 等必要数据，
 * 表单输入与结果面板的更新都不会穿过 memo 边界影响这里。
 */
export const OrderSidebar = memo(function OrderSidebar({
  orders,
  selectedId,
  loading,
  busy,
  refreshing,
  onSelect,
}: OrderSidebarProps) {
  return (
    <aside className="sidebar" aria-busy={loading || refreshing}>
      <div className="sidebar__title">
        <History size={16} strokeWidth={2} aria-hidden="true" />
        <h2>历史订单</h2>
        {!loading && orders.length > 0 && <span className="sidebar__count">{orders.length}</span>}
      </div>

      {loading ? (
        <ul className="order-list" aria-hidden="true">
          {SKELETON_ROWS.map(row => (
            <li key={row}>
              <div className="skeleton skeleton--order" />
            </li>
          ))}
        </ul>
      ) : orders.length === 0 ? (
        <p className="sidebar__empty">暂无历史订单</p>
      ) : (
        <ul className="order-list">
          {orders.map(order => (
            <OrderListItem
              key={order.order_id}
              order={order}
              selected={order.order_id === selectedId}
              busy={busy}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </aside>
  )
})
