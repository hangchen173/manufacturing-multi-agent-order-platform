import { memo } from 'react'
import { scoreClass } from '../lib/format'
import type { MatchedOrderItem } from '../types'

/**
 * 物料匹配结果表。
 *
 * 这里没有对每一行再做 memo：行内容随 items 整体替换而变化，
 * 逐行比较 props 只会增加开销，真正有效的隔离边界在 ResultPanel 与 items 的引用稳定性上。
 * 表格改用表头吸顶 + 外层滚动容器，长表格滚动时列含义不会丢失。
 */
export const MaterialTable = memo(function MaterialTable({ items }: { items: MatchedOrderItem[] }) {
  if (items.length === 0) {
    return <p className="empty">暂无可展示的物料匹配结果。</p>
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">行</th>
            <th scope="col">物料</th>
            <th scope="col">原始规格</th>
            <th scope="col">数量</th>
            <th scope="col" className="cell-num">单价</th>
            <th scope="col">标准 SKU / 候选</th>
            <th scope="col">标准物料 / 规格</th>
            <th scope="col" className="cell-num">匹配得分</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={index}>
              <td>{index + 1}</td>
              <td>{item.material_name}</td>
              <td>{item.specification || '未提供'}</td>
              <td>
                {item.quantity ?? '未提供'}
                {item.unit ? ` ${item.unit}` : ''}
              </td>
              <td className="cell-num">{item.unit_price ?? '未提供'}</td>
              <td>
                {item.sku_code || '未接受'}
                {!item.sku_code && (
                  <>
                    <small>{item.candidate_skus?.join('、') || '无候选'}</small>
                    <small>{item.rejection_reason}</small>
                  </>
                )}
              </td>
              <td>
                {item.matched_material_name || '-'}
                <small>{item.matched_specification || '-'}</small>
              </td>
              <td className="cell-num">
                <span className={scoreClass(item.match_score)}>{item.match_score.toFixed(2)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
})
