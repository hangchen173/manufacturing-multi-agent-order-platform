export type OrderStatus = 'pending' | 'parsing' | 'matching' | 'risk_checking' | 'needs_confirmation' | 'completed' | 'failed'

export interface OrderItem { material_name: string; specification?: string | null; quantity?: number | null; unit?: string | null; unit_price?: number | null; delivery_date?: string | null; confidence_score?: number | null }
export interface MatchedOrderItem extends OrderItem { sku_code?: string | null; matched_material_name?: string | null; matched_specification?: string | null; match_score: number; candidate_skus?: string[]; rejection_reason?: string | null }
export interface NormalizationChange { item_index: number; field: string; original_value: string; standard_value: string; basis: string }
export interface BusinessDecision { action: 'auto_approve' | 'auto_correct' | 'manual_review'; reason: string; normalizations: NormalizationChange[] }
export interface RiskIssue { item_index: number; issue_type: string; description: string; severity: string }
export interface FinalResult { status: OrderStatus; parsed_order?: { order_number?: string | null; customer_name?: string | null; items: OrderItem[]; total_amount?: number | null; parsing_confidence: number } | null; matched_order?: { items: MatchedOrderItem[] } | null; risk_result?: { needs_confirmation: boolean; issues: RiskIssue[]; overall_confidence: number } | null; business_decision?: BusinessDecision | null; message?: string | null }
export interface Transition { from_status?: OrderStatus | null; to_status: OrderStatus; timestamp: string; reason?: string | null }
export interface OrderSummary { order_id: string; status: OrderStatus; created_at: string; updated_at: string; document_type?: string | null; document_path?: string | null; confirmation_count: number; error_message?: string | null }
export interface OrderDetail extends OrderSummary { final_result?: FinalResult | null; confirmation_requests: Array<{ needs_confirmation_reasons?: string[]; issues?: RiskIssue[]; overall_confidence?: number }>; transition_history: Transition[]; review_actions?: Array<{ action: 'confirm' | 'reject'; comment?: string | null; timestamp: string }> }
