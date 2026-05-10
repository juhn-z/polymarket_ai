export type ResolveStatus = "active" | "resolved" | "expired";
export type Resolution = "yes" | "no" | null;
export type Direction = "bullish" | "bearish" | "neutral";
export type RecommendedAction = "buy_yes" | "buy_no" | "skip";
export type StrategyAction = "buy_yes" | "buy_no" | "skip";
export type StrategyStatus = "skipped" | "pending" | "executing" | "active" | "closed" | "failed";
export type TradeSide = "yes" | "no";
export type TradeAction = "buy" | "sell";
export type TradeStatus = "pending" | "filled" | "partial" | "cancelled" | "failed";
export type CloseReason = "take_profit" | "stop_loss" | "pre_resolution" | "manual" | null;

export interface MarketResponse {
  id: number;
  polymarket_condition_id: string;
  polymarket_token_id: string;
  event_slug: string;
  question: string;
  price_threshold: number;
  scan_date: string;        // ISO date
  target_date: string;      // ISO date
  current_yes_price: string;
  current_no_price: string;
  selected_at: string;      // ISO datetime
  status: ResolveStatus;
  resolution: Resolution;
}

export interface PredictionResponse {
  id: number;
  market_id: number;
  predicted_probability: string;
  confidence: string;
  direction: Direction;
  key_factors: string[];
  risk_factors: string[];
  technical_analysis: string;
  sentiment_analysis: string;
  news_impact: string;
  onchain_analysis: string;
  reasoning: string;
  recommended_action: RecommendedAction;
  market_probability: string;
  edge: string;
  model_version: string;
  prompt_version: string;
  seed: number;
  tokens_used: number;
  latency_ms: number;
  created_at: string;
}

export interface PredictionDetailResponse extends PredictionResponse {
  raw_request: Record<string, unknown>;
  raw_response: Record<string, unknown>;
  data_snapshot: Record<string, unknown>;
}

export interface StrategyResponse {
  id: number;
  prediction_id: number;
  market_id: number;
  action: StrategyAction;
  side: TradeSide | null;
  position_size: string;
  entry_price: string;
  take_profit: string;
  stop_loss: string;
  kelly_fraction: string;
  edge: string;
  skip_reason: string;
  status: StrategyStatus;
  created_at: string;
  executed_at: string | null;
}

export interface TradeResponse {
  id: number;
  strategy_id: number;
  market_id: number;
  polymarket_order_id: string;
  side: TradeSide;
  action: TradeAction;
  amount: string;
  price: string;
  shares: string;
  status: TradeStatus;
  fee: string;
  pnl: string | null;
  close_reason: CloseReason;
  created_at: string;
  filled_at: string | null;
  closed_at: string | null;
}

export interface OverviewResponse {
  tvl: string;
  share_price: string;
  total_pnl: string;
  total_trades: number;
  win_rate: string;
  active_positions: number;
}

export interface DailyPnLResponse {
  day: string;       // ISO date
  pnl: string;
  trade_count: number;
}

export interface VaultSnapshotResponse {
  id: number;
  total_assets: string;
  share_price: string;
  tvl: string;
  depositor_count: number;
  deployed_amount: string;
  snapshot_at: string;
}

export interface SystemStatusResponse {
  paused: boolean;
  scheduler_running: boolean;
  monitor_running: boolean;
}

export interface LeaderboardEntryResponse {
  rank: number;
  wallet: string;
  deposited: string;
  current_value: string;
  profit: string;
  profit_pct: string;
}
