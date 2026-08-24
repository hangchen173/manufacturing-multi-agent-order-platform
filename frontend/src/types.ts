export type OrderStatus = 'pending' | 'parsing' | 'matching' | 'risk_checking' | 'needs_confirmation' | 'completed' | 'failed'

export interface OrderItem { material_name: string; specification: string; quantity: number; unit: string; unit_price?: number | null; delivery_date?: string | null; confidence_score?: number | null }
export interface MatchedOrderItem extends OrderItem { sku_code?: string | null; matched_material_name?: string | null; match_score: number }
export interface RiskIssue { item_index: number; issue_type: string; description: string; severity: string }
export interface FinalResult { status: OrderStatus; parsed_order?: { order_number?: string | null; customer_name?: string | null; items: OrderItem[]; total_amount?: number | null; parsing_confidence: number } | null; matched_order?: { items: MatchedOrderItem[] } | null; risk_result?: { needs_confirmation: boolean; issues: RiskIssue[]; overall_confidence: number } | null; message?: string | null }
export interface Transition { from_status?: OrderStatus | null; to_status: OrderStatus; timestamp: string; reason?: string | null }
export interface OrderSummary { order_id: string; status: OrderStatus; created_at: string; updated_at: string; document_type?: string | null; confirmation_count: number; error_message?: string | null }
export interface OrderDetail extends OrderSummary { final_result?: FinalResult | null; confirmation_requests: Array<{ needs_confirmation_reasons?: string[]; issues?: RiskIssue[]; overall_confidence?: number }>; transition_history: Transition[] }
