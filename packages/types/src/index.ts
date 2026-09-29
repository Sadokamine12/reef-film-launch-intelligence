export type SourceLabel = 'LIVE'|'OBSERVED'|'HISTORICAL OBSERVATION'|'ESTIMATED'|'MODEL ESTIMATE'|'PLANNING ASSUMPTION'|'USER INPUT'|'CONFIRMED FACT'|'UNKNOWN';
export type Status = 'PRE_LAUNCH'|'DATA_NEEDED'|'ON_TRACK'|'WATCH'|'ACTION'|'NEAR_FULL'|'COMPLETE';
export interface Decision {status:Status;target_today:number;target_sales_today:number;recommended_budget_cents:number;daily_budget_cents:number;duration_days:number;channel:string;geography:string;creative:string;next_review:string;action:string;reason:string}
export interface ForecastEvidence {available?:boolean;method?:string;model_type?:string;rows?:number;unique_events?:number;validation?:{grouping:string;mae_tickets:number|null;mae_occupancy_pp:number|null};sources?:string[];limitations?:string[];[key:string]:unknown}
export interface Forecast {low:number|null;base:number|null;high:number|null;confidence:string;confidence_note:string;source_label:SourceLabel;required_sales_pace:number|null;gap_to_target:number|null;method:string;evidence?:ForecastEvidence|null;warnings?:string[];range_label?:string}
export interface CurvePoint {days:number;tickets:number}
export interface Screening {id:string;date:string;time:string|null;capacity:number;booking_url:string|null;sales_open_date:string|null;sales_open_confirmed:boolean;days_until:number;tickets_sold:number|null;seats_remaining:number|null;observed_at:string|null;source_label:SourceLabel;stale:boolean;velocity_3:number|null;velocity_7:number|null;acceleration:number|null;forecast:Forecast;decision:Decision;actual_curve:(CurvePoint&{observed_at:string})[]}
export interface Rules {curve:CurvePoint[];total_ceiling_cents:number;meta_ceiling_cents:number;google_ceiling_cents:number;reserve_cents:number;meta_test_cents:number;google_test_cents:number;watch_ratio:number;near_full_tickets:number;watch_daily_cents:number;action_daily_cents:number;campaign_days:number;stale_after_hours:number;paid_window_days:number;baseline_ticket_price_cents:number;attendance_target_pct:number;price_elasticity:number;price_elasticity_uncertainty:number;revenue_share_bps:number|null;fixed_cost_cents:number|null;variable_cost_per_ticket_cents:number|null;ad_incremental_cpa_cents:number|null;cannibalization_pct:number|null;sales_open_target:string;paid_test_start:string;paid_test_end:string}
export interface BudgetChannel {ceiling_cents:number;spent_cents:number;committed_cents:number;available_cents:number;over_ceiling:boolean}
export interface Budget {ceiling_cents:number;spent_cents:number;committed_cents:number;available_cents:number;reserve_cents:number;remaining_cents:number;over_ceiling:boolean;channels:Record<'META'|'GOOGLE',BudgetChannel>}
export interface Project {id:string;name:string;film:string;venue:string;latitude:number;longitude:number;timezone:string}
export interface Dashboard {as_of:string;project:Project;summary:{capacity:number;tickets_sold:number|null;known_tickets:number;observed_screenings:number;seats_remaining:number|null;target_today:number;recommended_budget_cents:number};today:Decision&{headline:string;screening_id:string};screenings:Screening[];budget:Budget;curve:CurvePoint[];rules:Rules;forecast_model:ForecastEvidence;revision:number}
export interface Performance {spend_cents:number;impressions:number;clicks:number;landing_page_views:number|null;attributed_tickets:number|null;ctr:number|null;landing_page_response:number|null;cost_per_ticket_cents:number|null;observations:number;source_label?:SourceLabel;last_imported_at?:string|null}
export interface Campaign {id:string;name:string;platform:'META'|'GOOGLE';ad_set:string;geography_id:string;audience:string;creative_id:string;screening_id:string;start_date:string;end_date:string;budget_cents:number;status:string;external_id:string|null;metrics:Performance}
export interface Creative {id:string;name:string;concept:string;headline:string;body:string;asset_url:string|null;status:'DRAFT'|'READY'|'RETIRED';performance:Performance}
export interface Geography {id:string;name:string;min_km:number;max_km:number;priority:string;notes:string;performance:Performance}
export interface Report {kind:string;title:string;generated_at:string;project:Project;rows:Record<string,string|number|null>[];notes:string[];recommendation:string}
export interface Historical {id:string;programme:string;show_date:string;observed_at:string;days_before:number;unavailable_seats:number;capacity:number;source_url:string}
export interface Integration {provider:string;status:string;label:SourceLabel;last_sync:string|null;detail:string}
export interface User {email:string;role:'viewer'|'editor';development:boolean}

export interface ScenarioScreening {
  id:string;date:string;capacity:number;observed_tickets:number|null;
  baseline_low:number|null;baseline_base:number;baseline_high:number|null;
  price_low:number;price_base:number;price_high:number;
  advertising_budget_cents:number;ad_increment_low:number;ad_increment_base:number;ad_increment_high:number;
  predicted_low:number;predicted_base:number;predicted_high:number;
  occupancy_low_pct:number;occupancy_base_pct:number;occupancy_high_pct:number;
  gross_revenue_base_cents:number;break_even_tickets_vs_baseline_full:number;meets_target:boolean;
  forecast_confidence:string;forecast_method:string|null;
}
export interface ScenarioPortfolio {
  capacity:number;tickets_low:number;tickets_base:number;tickets_high:number;
  occupancy_low_pct:number;occupancy_base_pct:number;occupancy_high_pct:number;
  gross_revenue_low_cents:number;gross_revenue_base_cents:number;gross_revenue_high_cents:number;
  advertising_budget_cents:number;reef_ticket_income_cents:number|null;variable_cost_cents:number|null;
  fixed_cost_cents:number|null;provisional_contribution_cents:number|null;economics_complete:boolean;
}
export interface ScenarioLadderRow {ticket_price_cents:number;tickets_base:number;occupancy_base_pct:number;gross_revenue_base_cents:number;meets_target:boolean}
export interface BudgetLadderRow {advertising_budget_cents:number;tickets_base:number;occupancy_base_pct:number;gross_revenue_base_cents:number}
export interface ScenarioEvidenceItem {classification:SourceLabel;[key:string]:unknown}
export interface ScenarioResult {
  screening_ids:string[];ticket_price_cents:number;baseline_ticket_price_cents:number;attendance_target_pct:number;advertising_budget_cents:number;
  screenings:ScenarioScreening[];portfolio:ScenarioPortfolio;price_ladder:ScenarioLadderRow[];budget_ladder:BudgetLadderRow[];
  highest_tested_price_meeting_target_cents:number|null;revenue_maximizing_tested_price_cents:number;
  evidence:{baseline_demand:ScenarioEvidenceItem;ticket_price:ScenarioEvidenceItem;price_response:ScenarioEvidenceItem;advertising_response:ScenarioEvidenceItem;economics:ScenarioEvidenceItem;cannibalization:ScenarioEvidenceItem};warnings:string[];
}
