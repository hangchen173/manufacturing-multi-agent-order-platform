import { memo } from 'react'
import { ClipboardList } from 'lucide-react'

export const AppHeader = memo(function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__mark" aria-hidden="true">
          <ClipboardList size={20} strokeWidth={2} />
        </span>
        <div>
          <span className="app-header__title">智能订单工作台</span>
          <span className="app-header__subtitle">制造业订单解析与风险审核</span>
        </div>
      </div>
    </header>
  )
})
