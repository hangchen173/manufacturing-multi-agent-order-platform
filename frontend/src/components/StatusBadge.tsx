import { memo } from 'react'
import { statusLabels } from '../lib/labels'
import type { OrderStatus } from '../types'

/**
 * 状态徽标。整个应用里出现频率最高的叶子组件，用 memo 隔离：
 * 侧栏列表滚动、表单输入等无关更新不会触发它重新渲染。
 */
export const StatusBadge = memo(function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`status status--${status}`}>
      <span className="status__dot" aria-hidden="true" />
      {statusLabels[status]}
    </span>
  )
})
