export interface AuditThresholdsConfig {
  revenue_drop_sigma: number;
  churn_cadence_multiplier: number;
  churn_min_purchases: number;
  trend_decoupling_pct: number;
  seasonality_min_months: number;
  materiality_revenue_pct: number;
  rfm_bins: number;
  variable_cost_pct: number;
  latent_revenue_anchor_category: string;
  latent_revenue_target_category: string;
  latent_revenue_conversion_pct: number;
  dead_stock_months: number;
  contingency_completeness_pct: number;
  outlier_median_ratio: number;
  cold_start_min_months: number;
  sev_min_capture_pct: number;
  sev_ramp_min_days: number;
  concentration_risk_pct: number;
  service_category_label: string;
  service_reconciliation_gap_tolerance: number;
}

export interface WinsorizedValue {
  source_file: string;
  source_row: number;
  product: string;
  original_value: number;
  capped_value: number;
}

export interface CleaningSummary {
  rows_read: number;
  rows_accepted: number;
  rows_discarded_by_reason: Record<string, number>;
  files_skipped: Record<string, any>[];
  values_winsorized: WinsorizedValue[];
}

export interface RevenueLeakAnomaly {
  scope: string;
  entity_id: string;
  period: string;
  expected_value: number;
  actual_value: number;
  drop_sigma: number;
  seasonality_adjusted: boolean;
  confidence: string;
  severity: string;
  low_confidence: boolean;
}

export interface ChurnFinding {
  customer_id: string;
  purchase_count: number;
  avg_cadence_days: number;
  last_purchase: string;
  months_silent: number;
  historical_annual_value: number;
}

export interface ProductTrendEntry {
  product: string;
  company_growth_pct: number;
  product_growth_pct: number;
  decoupled: boolean;
  last_sale_month: string | null;
}

export interface RFMChampion {
  customer_id: string;
  recency_days: number;
  frequency: number;
  monetary: number;
  recency_score: number;
  frequency_score: number;
  monetary_score: number;
}

export interface ContributionMarginAlert {
  product: string;
  avg_price: number;
  avg_entry_cost: number;
  variable_cost_pct: number;
  contribution_margin: number;
  sample_size: number;
}

export interface LatentRevenueFinding {
  anchor_category: string;
  target_category: string;
  eligible_customers: number;
  non_buyers_count: number;
  attach_rate_pct: number;
  avg_ticket_target_category: number;
  assumed_conversion_pct: number;
  estimated_latent_revenue: number;
  non_buyer_customers: string[];
}

export interface SeasonalityCurve {
  scope: string;
  entity: string;
  monthly_index: Record<number, number> | null;
  insufficient_data: boolean;
  months_available: number | null;
}

export interface DeadStockFinding {
  dead_stock_months: number;
  sku_count: number;
  capital_frozen: number;
  total_inventory_value: number;
  dead_stock_pct: number;
  skus: string[];
}

export interface GmroiEntry {
  category: string;
  gross_margin: number;
  avg_inventory_value: number;
  gmroi: number | null;
  sample_size: number;
  is_directional_only: boolean;
}

export interface StorePerformance {
  store: string;
  gross_revenue: number;
  revenue_sample_size: number;
  avg_price: number;
  avg_entry_cost: number;
  variable_cost_pct: number;
  contribution_margin_avg: number;
  contribution_margin_total: number;
  margin_sample_size: number;
  months_of_history: number;
  has_sufficient_history: boolean;
}

export interface StoreMacroSummary {
  stores_with_negative_margin: string[];
  masked_amount: number;
  network_contribution_margin_total: number;
  revenue_rank: string[];
  margin_rank: string[];
  rank_differs: boolean;
}

export interface CustomerConcentrationFinding {
  store: string;
  customer: string;
  customer_revenue: number;
  store_revenue: number;
  concentration_pct: number;
  sample_size: number;
}

export interface SalespersonPerformance {
  salesperson: string;
  total_revenue: number;
  sample_size: number;
  capture_rate_pct: number;
  low_capture_flag: boolean;
  days_since_first_sale: number;
  has_sufficient_tenure: boolean;
  low_volume_flag: boolean;
}

export interface DataCompletenessFinding {
  total_customers: number;
  phone_filled_pct: number;
  document_filled_pct: number;
  completeness_pct: number;
  contingency_triggered: boolean;
}

export interface ServiceDecomposition {
  store: string;
  product_margin: number;
  service_margin: number;
  total_margin: number;
  masks_negative_product_margin: boolean;
  follow_on_cac_effect: number;
}

export interface ServiceReconciliation {
  store: string;
  period: string;
  financial_declared_revenue: number;
  sales_transactional_revenue: number;
  gap: number;
  has_gap: boolean;
}

export interface DiscardedAlarm {
  category: 'salesperson_ramp' | 'store_cold_start';
  entity_id: string;
  reason: string;
}

export interface ActionPlanItem {
  id: string;
  category: string;
  title: string;
  description: string;
  impact_brl: number;
  nature: 'operational' | 'capital' | 'ltv_risk';
  tier: number;
}

export interface ExecutiveSummary {
  total_operational_loss: number;
  total_capital_frozen: number;
  total_ltv_risk: number;
  discarded_alarms: DiscardedAlarm[];
  action_plan: ActionPlanItem[];
}

export interface ExecutiveAuditReport {
  period_start: string;
  period_end: string;
  cleaning: CleaningSummary;
  thresholds: AuditThresholdsConfig;
  revenue_leaks: RevenueLeakAnomaly[];
  churn_findings: ChurnFinding[];
  product_trends: ProductTrendEntry[];
  seasonality: SeasonalityCurve[];
  rfm_champions: RFMChampion[];
  contribution_margin_alerts: ContributionMarginAlert[];
  latent_revenue: LatentRevenueFinding[];
  dead_stock: DeadStockFinding[];
  gmroi: GmroiEntry[];
  data_completeness: DataCompletenessFinding[];
  store_performance: StorePerformance[];
  store_macro_summary: StoreMacroSummary | null;
  customer_concentration: CustomerConcentrationFinding[];
  service_decomposition: ServiceDecomposition[];
  service_reconciliation: ServiceReconciliation[];
  salesperson_performance: SalespersonPerformance[];
  executive_summary: ExecutiveSummary;
  generated_at: string;
}
