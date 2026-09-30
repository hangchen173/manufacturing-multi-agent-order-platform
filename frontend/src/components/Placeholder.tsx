import { memo } from 'react'
import { ClipboardList, LoaderCircle } from 'lucide-react'
import type { InputMode } from '../hooks/useOrderConsole'

/** 处理中占位。role="status" 让读屏用户获知后台正在执行。 */
export const ProcessingPlaceholder = memo(function ProcessingPlaceholder({
  mode,
  fileName,
}: {
  mode: InputMode
  fileName?: string
}) {
  return (
    <section className="panel panel--placeholder" role="status">
      <LoaderCircle className="spin" size={30} strokeWidth={1.8} aria-hidden="true" />
      <h2>正在处理{mode === 'file' && fileName ? `：${fileName}` : '订单'}</h2>
      <p>解析、物料匹配与风险审核正在后台执行，通常需要数秒。</p>
    </section>
  )
})

export const IdlePlaceholder = memo(function IdlePlaceholder() {
  return (
    <section className="panel panel--placeholder">
      <ClipboardList size={30} strokeWidth={1.8} aria-hidden="true" />
      <h2>等待订单处理</h2>
      <p>提交新订单，或从左侧选择一条历史订单查看完整处理结果。</p>
    </section>
  )
})
