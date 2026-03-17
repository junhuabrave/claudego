import axios from "axios";
import { getOrCreateSessionId } from "../contexts/AuthContext";
import type { CandlePoint, ChatResponse, IPOEvent, NewsArticle, PriceAlert, Reminder, Ticker } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const client = axios.create({ baseURL: API_URL });

// Attach auth headers on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("finmonitor_token");
  const sessionId = getOrCreateSessionId();
  if (token) config.headers["Authorization"] = `Bearer ${token}`;
  config.headers["X-Session-ID"] = sessionId;
  return config;
});

// --- Tickers ---
export const getTickers = () => client.get<Ticker[]>("/tickers").then((r) => r.data);

export const addTicker = (symbol: string, name?: string) =>
  client.post<Ticker>("/tickers", { symbol, name: name || "" }).then((r) => r.data);

export const removeTicker = (symbol: string) => client.delete(`/tickers/${symbol}`);

// --- News ---
export interface NewsPage {
  articles: NewsArticle[];
  total: number;
}

export const getNews = (limit = 20, offset = 0): Promise<NewsPage> =>
  client.get<NewsArticle[]>("/news", { params: { limit, offset } }).then((r) => ({
    articles: r.data,
    total: parseInt(r.headers["x-total-count"] ?? "0", 10),
  }));

// --- IPOs ---
export const getIPOs = () => client.get<IPOEvent[]>("/ipos").then((r) => r.data);

// --- Reminders ---
export const getReminders = () => client.get<Reminder[]>("/reminders").then((r) => r.data);

export const createReminder = (data: {
  ipo_event_id: number;
  notify_via: string;
  notify_address: string;
  remind_before_hours?: number;
}) => client.post<Reminder>("/reminders", data).then((r) => r.data);

export const deleteReminder = (id: number) => client.delete(`/reminders/${id}`);

// --- Candles ---
export const getCandles = (symbol: string, resolution = "5", days = 1) =>
  client
    .get<CandlePoint[]>(`/candles/${symbol}`, { params: { resolution, days } })
    .then((r) => r.data);

// --- Chat ---
export const sendChatMessage = (message: string) =>
  client.post<ChatResponse>("/chat", { message }).then((r) => r.data);

// --- Price Alerts ---
export const alertsApi = {
  list: () => client.get<PriceAlert[]>("/alerts").then((r) => r.data),

  create: (payload: { symbol: string; threshold_pct: number; direction: string }) =>
    client.post<PriceAlert>("/alerts", payload).then((r) => r.data),

  update: (
    id: number,
    payload: Partial<{ threshold_pct: number; direction: string; is_active: boolean }>
  ) => client.put<PriceAlert>(`/alerts/${id}`, payload).then((r) => r.data),

  remove: (id: number): Promise<void> =>
    client.delete(`/alerts/${id}`).then(() => undefined),
};
