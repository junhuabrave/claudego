import axios from "axios";
import type { CandlePoint, ChatResponse, IPOEvent, NewsArticle, Reminder, Ticker } from "../types";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

const client = axios.create({ baseURL: API_URL });

// --- Tickers ---
export const getTickers = () => client.get<Ticker[]>("/tickers").then((r) => r.data);

export const addTicker = (symbol: string, name?: string) =>
  client.post<Ticker>("/tickers", { symbol, name: name || "" }).then((r) => r.data);

export const removeTicker = (symbol: string) => client.delete(`/tickers/${symbol}`);

// --- News ---
export const getNews = (limit = 50) =>
  client.get<NewsArticle[]>("/news", { params: { limit } }).then((r) => r.data);

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
