export interface Ticker {
  id: number;
  symbol: string;
  name: string;
  exchange: string;
  last_price: number | null;
  change_percent: number | null;
  active: boolean;
  created_at: string;
}

export interface NewsArticle {
  id: number;
  external_id: string;
  headline: string;
  summary: string;
  source: string;
  url: string;
  image_url: string;
  category: string;
  related_tickers: string;
  sentiment: string;
  published_at: string;
  created_at: string;
}

export interface IPOEvent {
  id: number;
  company_name: string;
  symbol: string;
  exchange: string;
  price_range: string;
  shares_offered: string;
  expected_date: string;
  status: string;
  created_at: string;
}

export interface Reminder {
  id: number;
  ipo_event_id: number;
  notify_via: "email" | "pagerduty";
  notify_address: string;
  remind_before_hours: number;
  sent: boolean;
  created_at: string;
}

export interface ChatResponse {
  reply: string;
  action: string | null;
  ticker: string | null;
}

export interface CandlePoint {
  t: number; // Unix timestamp (seconds)
  o: number; // Open
  h: number; // High
  l: number; // Low
  c: number; // Close
  v: number; // Volume
}

export interface WSMessage {
  type: "news" | "quotes" | "ipo_update" | "pong";
  data: Record<string, unknown>;
}
