import { memo } from 'react'
import { severityLabel } from '../lib/labels'
import type { RiskIssue } from '../types'

export const RiskIssues = memo(function RiskIssues({ issues }: { issues: RiskIssue[] }) {
  if (issues.length === 0) return null

  return (
    <section className="result-section defer-paint">
      <h3>风险问题</h3>
      {issues.map((issue, index) => (
        <p className="issue" key={`${issue.item_index}-${issue.issue_type}-${index}`}>
          <span className={`severity severity--${issue.severity}`}>{severityLabel(issue.severity)}</span>
          {issue.item_index < 0 ? '整单' : `第 ${issue.item_index + 1} 项`}：{issue.description}
        </p>
      ))}
    </section>
  )
})
