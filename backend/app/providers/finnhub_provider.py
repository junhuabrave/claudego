"""Finnhub.io provider for news, quotes, and IPO data."""

import asyncio
import datetime
import math

import httpx
import yfinance as yf

from app.core.config import settings
from app.providers.base import IPOProvider, NewsProvider, QuoteProvider
from app.providers.symbol_mapper import to_finnhub

BASE_URL = "https://finnhub.io/api/v1"


class FinnhubNewsProvider(NewsProvider):
    async def fetch_market_news(self, category: str = "general") -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/news",
                params={"category": category, "token": settings.finnhub_api_key},
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json()

        return [
            {
                "external_id": f"finnhub-{item['id']}",
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "image_url": item.get("image", ""),
                "category": item.get("category", category),
                "related_tickers": item.get("related", ""),
                "sentiment": "neutral",
                "published_at": datetime.datetime.fromtimestamp(
                    item.get("datetime", 0), tz=datetime.timezone.utc
                ),
            }
            for item in items[:50]
        ]

    async def fetch_news_for_ticker(self, symbol: str) -> list[dict]:
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/company-news",
                params={
                    "symbol": to_finnhub(symbol),
                    "from": week_ago.isoformat(),
                    "to": today.isoformat(),
                    "token": settings.finnhub_api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json()

        return [
            {
                "external_id": f"finnhub-{item['id']}",
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "image_url": item.get("image", ""),
                "category": "company",
                "related_tickers": symbol,
                "sentiment": "neutral",
                "published_at": datetime.datetime.fromtimestamp(
                    item.get("datetime", 0), tz=datetime.timezone.utc
                ),
            }
            for item in items[:20]
        ]


async def _yfinance_quote(symbol: str) -> dict:
    """Fallback quote fetch via yfinance when Finnhub returns zero price."""

    def _fetch():
        t = yf.Ticker(symbol)
        fi = t.fast_info
        price = fi.last_price
        prev = fi.previous_close
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        return price, change_pct

    def _safe(val: float | None) -> float:
        """Return 0 for None, nan, or inf — values that break JSON serialization."""
        return val if (val is not None and math.isfinite(val)) else 0.0

    try:
        price, change_pct = await asyncio.get_event_loop().run_in_executor(None, _fetch)
        return {"symbol": symbol, "price": _safe(price), "change_percent": _safe(change_pct)}
    except Exception:
        return {"symbol": symbol, "price": 0, "change_percent": 0}


class FinnhubQuoteProvider(QuoteProvider):
    async def fetch_quote(self, symbol: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/quote",
                params={"symbol": to_finnhub(symbol), "token": settings.finnhub_api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        price = data.get("c", 0)
        if not price:
            return await _yfinance_quote(symbol)

        return {
            "symbol": symbol,
            "price": price,
            "change_percent": data.get("dp", 0),
        }

    async def fetch_quotes_batch(self, symbols: list[str]) -> list[dict]:
        results = []
        async with httpx.AsyncClient() as client:
            for symbol in symbols:
                try:
                    resp = await client.get(
                        f"{BASE_URL}/quote",
                        params={"symbol": to_finnhub(symbol), "token": settings.finnhub_api_key},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    price = data.get("c", 0)
                    if price:
                        results.append(
                            {
                                "symbol": symbol,
                                "price": price,
                                "change_percent": data.get("dp", 0),
                            }
                        )
                    else:
                        results.append(await _yfinance_quote(symbol))
                except httpx.HTTPError:
                    results.append(await _yfinance_quote(symbol))
        return results


class FinnhubIPOProvider(IPOProvider):
    async def fetch_upcoming_ipos(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/calendar/ipo",
                params={
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat(),
                    "token": settings.finnhub_api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        ipo_calendar = data.get("ipoCalendar", [])
        return [
            {
                "external_id": f"finnhub-ipo-{item.get('name', '')}-{item.get('date', '')}",
                "company_name": item.get("name", ""),
                "symbol": item.get("symbol", ""),
                "exchange": item.get("exchange", ""),
                "price_range": item.get("price", ""),
                "shares_offered": str(item.get("numberOfShares", "")),
                "expected_date": item.get("date", from_date.isoformat()),
                "status": item.get("status", "expected"),
            }
            for item in ipo_calendar
        ]
