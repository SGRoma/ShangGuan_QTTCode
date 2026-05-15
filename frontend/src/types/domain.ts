export type AnyRecord = Record<string, any>;

export interface DashboardSummary {
  cards: Record<string, number>;
  latest_backtests: AnyRecord[];
  guardrails: string[];
}

export interface SeriesPoint {
  trade_date: string;
  close?: number;
  score?: number;
  position?: number;
  equity_curve?: number;
  benchmark_curve?: number;
  drawdown?: number;
  ma20?: number;
  ma60?: number;
  volume_ratio?: number;
  signal?: string;
  risk_level?: string;
}

export interface OperationState {
  stocks: AnyRecord[];
  strategies: AnyRecord[];
  backtests: AnyRecord[];
  datasets: AnyRecord[];
  training_samples?: AnyRecord[];
  models: AnyRecord[];
  agent_logs: AnyRecord[];
  dirty_records: AnyRecord[];
  data_models?: AnyRecord[];
  analysis_models?: AnyRecord[];
  summary: Record<string, number>;
  guardrails: string[];
}

export interface WorkflowPayload {
  step: string;
  stock_monitor: AnyRecord;
  strategy_version: AnyRecord;
  backtest: AnyRecord;
  dataset: AnyRecord;
  sample: AnyRecord;
  model: AnyRecord;
  simulation: AnyRecord;
  agent_review: AnyRecord;
  operation_state: OperationState;
}
