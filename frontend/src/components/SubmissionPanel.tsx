import { memo, useCallback, useState } from 'react'
import type { ChangeEvent } from 'react'
import { FileUp, LoaderCircle, Send, ShieldAlert } from 'lucide-react'
import type { InputMode, SubmissionRequest } from '../hooks/useOrderConsole'

const ACCEPTED_TYPES = '.txt,.csv,.pdf,.xlsx,.xls,.png,.jpg,.jpeg'

const SAMPLE_TEXT =
  '订单编号: ORD-2026-001\n客户: XX制造公司\n物料: 不锈钢螺丝 M8x30, 数量: 1000, 单价: 0.5, 交期: 2026-09-30'

interface SubmissionPanelProps {
  busy: boolean
  error: string
  onReset: () => void
  onSubmit: (request: SubmissionRequest) => void
}

/**
 * 提交面板。
 *
 * 输入草稿（输入方式 / 文本 / 文件）刻意保留在本组件内部，而不是提升到 App：
 * 这样每次按键只重渲染这一块表单，侧栏与结果面板不受影响，
 * 输入延迟与树规模解耦。
 */
export const SubmissionPanel = memo(function SubmissionPanel({
  busy,
  error,
  onReset,
  onSubmit,
}: SubmissionPanelProps) {
  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const changeMode = useCallback(
    (next: InputMode) => {
      setMode(next)
      onReset()
    },
    [onReset],
  )

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      setFile(event.target.files?.[0] ?? null)
      onReset()
    },
    [onReset],
  )

  const handleSubmit = useCallback(() => {
    onSubmit({ mode, text, file })
  }, [file, mode, onSubmit, text])

  return (
    <section className="panel panel--submission">
      <div className="section-heading">
        <div>
          <p className="eyebrow">新订单</p>
          <h1>提交待解析订单</h1>
        </div>
      </div>

      <div className="segmented">
        <button
          type="button"
          className={mode === 'text' ? 'segmented__item segmented__item--active' : 'segmented__item'}
          aria-pressed={mode === 'text'}
          disabled={busy}
          onClick={() => changeMode('text')}
        >
          粘贴文本
        </button>
        <button
          type="button"
          className={mode === 'file' ? 'segmented__item segmented__item--active' : 'segmented__item'}
          aria-pressed={mode === 'file'}
          disabled={busy}
          onClick={() => changeMode('file')}
        >
          上传文件
        </button>
      </div>

      {mode === 'text' ? (
        <textarea
          className="field-textarea"
          aria-label="订单文本"
          disabled={busy}
          value={text}
          onChange={event => setText(event.target.value)}
          placeholder={SAMPLE_TEXT}
        />
      ) : (
        <label className="file-drop" htmlFor="order-file">
          <FileUp size={24} strokeWidth={1.8} aria-hidden="true" />
          <strong>{file ? file.name : '选择订单文件'}</strong>
          <span>PDF、Excel、图片、TXT 或 CSV，最大 16 MB</span>
          <input
            id="order-file"
            aria-label="订单文件"
            disabled={busy}
            type="file"
            accept={ACCEPTED_TYPES}
            onChange={handleFileChange}
          />
        </label>
      )}

      {error && (
        <div className="alert alert--error" role="alert">
          <ShieldAlert size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <button type="button" className="button button--primary" disabled={busy} aria-busy={busy} onClick={handleSubmit}>
        {busy ? (
          <LoaderCircle className="spin" size={17} aria-hidden="true" />
        ) : (
          <Send size={17} aria-hidden="true" />
        )}
        {busy ? '处理中…' : '开始解析'}
      </button>
    </section>
  )
})
