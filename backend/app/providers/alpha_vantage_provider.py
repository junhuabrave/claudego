"""Alpha Vantage provider for IPO calendar data.

The IPO_CALENDAR endpoint is available on the free tier (25 req/day).
It returns CSV with all upcoming IPOs; we filter client-side by date range.

CSV columns: symbol, name, ipoDate, priceRangeLow, priceRangeHigh, currency, exchange
"""

import csv
import datetime
import io
import logging

import httpx

from app.core.config import settings
from app.providers.base import IPOProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageIPOProvider(IPOProvider):
    async def fetch_upcoming_ipos(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> list[dict]:
        if not settings.alpha_vantage_api_key:
            logger.warning("alpha_vantage_api_key not set — skipping IPO fetch")
            return []

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                BASE_URL,
                params={
                    "function": "IPO_CALENDAR",
                    "apikey": settings.alpha_vantage_api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        results = []
        for row in reader:
            raw_date = row.get("ipoDate", "")
            try:
                ipo_date = datetime.date.fromisoformat(raw_date)
            except ValueError:
                continue  # skip rows with unparseable dates

            if not (from_date <= ipo_date <= to_date):
                continue

            symbol = row.get("symbol", "")
            name = row.get("name", "")
            low = row.get("priceRangeLow", "")
            high = row.get("priceRangeHigh", "")
            price_range = f"{low}-{high}" if low and high else low or high

            results.append(
                {
                    "external_id": f"av-ipo-{symbol}-{raw_date}",
                    "company_name": name,
                    "symbol": symbol,
                    "exchange": row.get("exchange", ""),
                    "price_range": price_range,
                    "shares_offered": "",  # not provided by this endpoint
                    "expected_date": ipo_date,
                    "status": "expected",
                }
            )

        return results
