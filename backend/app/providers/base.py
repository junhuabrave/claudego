"""Abstract base classes for data providers.

All providers implement these interfaces so we can swap
free APIs for premium ones by changing configuration only.
"""

import abc
import datetime


class NewsProvider(abc.ABC):
    @abc.abstractmethod
    async def fetch_market_news(self, category: str = "general") -> list[dict]:
        """Return list of news dicts with keys:
        external_id, headline, summary, source, url, image_url,
        category, related_tickers, sentiment, published_at
        """

    @abc.abstractmethod
    async def fetch_news_for_ticker(self, symbol: str) -> list[dict]:
        """Return news related to a specific ticker."""


class QuoteProvider(abc.ABC):
    @abc.abstractmethod
    async def fetch_quote(self, symbol: str) -> dict:
        """Return dict with keys: symbol, price, change_percent."""

    @abc.abstractmethod
    async def fetch_quotes_batch(self, symbols: list[str]) -> list[dict]:
        """Return quotes for multiple symbols."""


class IPOProvider(abc.ABC):
    @abc.abstractmethod
    async def fetch_upcoming_ipos(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> list[dict]:
        """Return list of IPO dicts with keys:
        external_id, company_name, symbol, exchange,
        price_range, shares_offered, expected_date, status
        """
