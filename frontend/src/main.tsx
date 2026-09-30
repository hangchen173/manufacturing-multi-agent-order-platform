import { AppHeader } from './components/AppHeader'
import { IdlePlaceholder, ProcessingPlaceholder } from './components/Placeholder'
import { OrderSidebar } from './components/OrderSidebar'
import { ResultPanel } from './components/ResultPanel'
import { SubmissionPanel } from './components/SubmissionPanel'
import { useOrderConsole } from './hooks/useOrderConsole'
import './styles/index.css'

/**
 * 应用外壳：只负责把状态 hook 的结果分发给各区块。
 * 所有子组件都是 memo 化的，状态变化只影响真正依赖它的那一块。
 */
export default function App() {
  const {
    orders,
    selected,
    selectedId,
    pending,
    error,
    historyLoading,
    refreshing,
    busy,
    selectOrder,
    submit,
    confirm,
    clearResult,
  } = useOrderConsole()

  return (
    <main>
      <AppHeader />
      <div className="app__layout">
        <OrderSidebar
          orders={orders}
          selectedId={selectedId}
          loading={historyLoading}
          busy={busy}
          refreshing={refreshing}
          onSelect={selectOrder}
        />
        <div className="workspace">
          <SubmissionPanel busy={busy} error={error} onReset={clearResult} onSubmit={submit} />
          {busy && !selected ? (
            <ProcessingPlaceholder mode={pending?.mode ?? 'text'} fileName={pending?.fileName} />
          ) : selected ? (
            <ResultPanel order={selected} busy={busy} onConfirm={confirm} />
          ) : (
            <IdlePlaceholder />
          )}
        </div>
      </div>
    </main>
  )
}
