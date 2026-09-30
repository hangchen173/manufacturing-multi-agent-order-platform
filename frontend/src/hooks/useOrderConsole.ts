import { useCallback, useEffect, useRef, useState, useTransition } from 'react'
import { api } from '../api'
import { errorMessage, errorOrderId } from '../lib/format'
import type { OrderDetail, OrderSummary } from '../types'

export type InputMode = 'text' | 'file'

export interface SubmissionRequest {
  mode: InputMode
  text: string
  file: File | null
}

/** 正在处理的任务描述，用于占位面板展示上下文。 */
export interface PendingTask {
  mode: InputMode
  fileName?: string
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

/**
 * 订单工作台的全部服务端状态与副作用集中在这里。
 *
 * 与视图分离后带来两个直接收益：
 * 1. 组件只负责渲染，交互逻辑可单独测试；
 * 2. 输入草稿（文本 / 文件 / 输入方式）留在 SubmissionPanel 内部，
 *    因此每次敲键盘只重渲染表单本身，不会波及侧栏列表和结果面板。
 */
export function useOrderConsole() {
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [selected, setSelected] = useState<OrderDetail | null>(null)
  const [error, setError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [pending, setPending] = useState<PendingTask | null>(null)

  // 列表刷新属于非紧急更新：放进 transition 后，提交按钮的忙碌态能立即反馈，
  // 列表随后静默补全，不阻塞用户输入。
  const [isRefreshing, startTransition] = useTransition()

  const listAbort = useRef<AbortController | null>(null)
  const detailAbort = useRef<AbortController | null>(null)

  const loadOrders = useCallback(async () => {
    listAbort.current?.abort()
    const controller = new AbortController()
    listAbort.current = controller
    setHistoryLoading(true)
    try {
      const next = await api.listOrders(controller.signal)
      startTransition(() => setOrders(next))
    } catch (caught) {
      if (!isAbortError(caught)) setError(errorMessage(caught, '无法加载历史订单'))
    } finally {
      if (listAbort.current === controller) setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadOrders()
    return () => {
      listAbort.current?.abort()
      detailAbort.current?.abort()
    }
  }, [loadOrders])

  const selectOrder = useCallback(async (orderId: string) => {
    // 取消上一次未完成的详情请求：快速连点历史订单时不会浪费带宽，
    // 也不会把过期结果写回界面。
    detailAbort.current?.abort()
    const controller = new AbortController()
    detailAbort.current = controller
    setError('')
    setSelected(null)
    try {
      const order = await api.getOrder(orderId, controller.signal)
      if (detailAbort.current === controller) setSelected(order)
    } catch (caught) {
      if (!isAbortError(caught) && detailAbort.current === controller) {
        setError(errorMessage(caught, '无法加载订单详情'))
      }
    }
  }, [])

  const clearResult = useCallback(() => {
    detailAbort.current?.abort()
    detailAbort.current = null
    setSelected(null)
    setError('')
  }, [])

  const submit = useCallback(
    async ({ mode, text, file }: SubmissionRequest) => {
      if (mode === 'text' && !text.trim()) {
        setError('请输入订单文本')
        return
      }
      if (mode === 'file' && !file) {
        setError('请选择订单文件')
        return
      }
      clearResult()
      setPending({ mode, fileName: file?.name })
      setSubmitting(true)
      try {
        const result = mode === 'text' ? await api.submitText(text) : await api.submitFile(file as File)
        await selectOrder(result.order_id)
        await loadOrders()
      } catch (caught) {
        // 服务端可能已经落库并回传 order_id，此时仍要把详情拉出来给操作员看。
        const failedOrderId = errorOrderId(caught)
        if (failedOrderId) await selectOrder(failedOrderId)
        await loadOrders()
        setError(errorMessage(caught, '订单提交失败'))
      } finally {
        setSubmitting(false)
        setPending(null)
      }
    },
    [clearResult, loadOrders, selectOrder],
  )

  const selectedId = selected?.order_id ?? null

  const confirm = useCallback(
    async (action: 'confirm' | 'reject') => {
      if (!selectedId) return
      setConfirming(true)
      setError('')
      try {
        await api.confirm(selectedId, action)
        await selectOrder(selectedId)
        await loadOrders()
      } catch (caught) {
        setError(errorMessage(caught, '操作失败'))
      } finally {
        setConfirming(false)
      }
    },
    [loadOrders, selectOrder, selectedId],
  )

  return {
    orders,
    selected,
    selectedId,
    pending,
    error,
    historyLoading,
    refreshing: isRefreshing,
    busy: submitting || confirming,
    selectOrder,
    submit,
    confirm,
    clearResult,
  }
}

export type OrderConsole = ReturnType<typeof useOrderConsole>
