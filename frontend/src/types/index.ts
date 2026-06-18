export type AccountRole = 'MASTER' | 'SLAVE';
export type RiskMode = 'FIXED' | 'RISK_PERCENT' | 'RISK_USD' | 'RISK_OF_MASTER' | 'RATIO' | 'BALANCE_PROP';
export type SymbolMode = 'ALL' | 'WHITELIST' | 'BLACKLIST';

export interface Account {
  id: string;
  name: string;
  role: AccountRole;
  login: number;
  server: string;
  terminal_path: string;
  poll_interval: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AccountForm {
  name: string;
  role: AccountRole;
  login: number;
  password: string;
  server: string;
  terminal_path: string;
  poll_interval: number;
  active: boolean;
}

export interface SlaveConfig {
  id: string;
  account_id: string;
  risk_mode: RiskMode;
  fixed_lots: number;
  risk_percent: number;
  risk_usd: number;
  lot_multiplier: number;
  max_lots: number;
  max_positions: number;
  max_drawdown_pct: number | null;
  daily_loss_limit: number | null;
  autocopy_enable: boolean;
  copy_sl: boolean;
  copy_tp: boolean;
  inverse_copy: boolean;
  delay_sec: number;
  symbol_mode: SymbolMode;
  symbol_filter: string[];
  order_comment: string | null;
  magic_number: number;
}

export interface CopierStatus {
  running: boolean;
  uptime_seconds: number | null;
  active_masters: number;
  active_slaves: number;
  total_positions: number;
  last_error: string | null;
}

export interface TradeLog {
  id: string;
  timestamp: string;
  master_account_id: string | null;
  slave_account_id: string | null;
  action: string;
  symbol: string;
  volume: number;
  price: number;
  sl: number | null;
  tp: number | null;
  result: string;
  error_code: number | null;
  error_message: string | null;
}

export interface Position {
  id: string;
  master_ticket: number;
  master_account_id: string;
  slave_account_id: string;
  slave_ticket: number | null;
  symbol: string;
  volume: number;
  price_open: number;
  direction: string;
  status: string;
  created_at: string;
  closed_at: string | null;
}

export interface SymbolMapEntry {
  id: string;
  base_symbol: string;
  broker_server: string;
  broker_symbol: string;
}

export interface WSMessage {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface TestResult {
  success: boolean;
  message: string;
  balance: number | null;
  equity: number | null;
  server: string | null;
}

export interface SlaveMasterLink {
  slave_id: string;
  master_id: string;
  active: boolean;
}
