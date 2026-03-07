"""Test H — Provider Adapters (Mocked HTTP)

Covers: FinnhubNewsProvider, FinnhubQuoteProvider, FinnhubIPOProvider,
AlphaVantageIPOProvider, provider factory, and symbol mapper.
All HTTP calls are mocked — no real API requests.
"""

import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.providers.alpha_vantage_provider import AlphaVantageIPOProvider
from app.providers.factory import get_ipo_provider, get_news_provider, get_quote_provider
from app.providers.finnhub_provider import (
    FinnhubIPOProvider,
    FinnhubNewsProvider,
    FinnhubQuoteProvider,
)
from app.providers.symbol_mapper import to_finnhub


# ---------------------------------------------------------------------------
# Symbol Mapper
# ---------------------------------------------------------------------------

class TestSymbolMapper:
    def test_us_stock_passthrough(self):
        assert to_finnhub("AAPL") == "AAPL"

    def test_london_stock(self):
        assert to_finnhub("VOD.L") == "LSE:VOD"

    def test_german_stock(self):
        assert to_finnhub("BMW.DE") == "XETR:BMW"

    def test_hong_kong_stock(self):
        assert to_finnhub("0005.HK") == "HKEX:0005"

    def test_tokyo_stock(self):
        assert to_finnhub("7203.T") == "TSE:7203"

    def test_already_finnhub_format(self):
        assert to_finnhub("LSE:VOD") == "LSE:VOD"

    def test_unknown_suffix_passthrough(self):
        assert to_finnhub("XYZ.ZZ") == "XYZ.ZZ"

    def test_no_dot_no_colon(self):
        assert to_finnhub("TSLA") == "TSLA"

    def test_korean_stock(self):
        assert to_finnhub("005930.KS") == "XKRX:005930"

    def test_brazilian_stock(self):
        assert to_finnhub("PETR4.SA") == "BVMF:PETR4"

    def test_toronto_stock(self):
        assert to_finnhub("RY.TO") == "XTSE:RY"


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------

class TestProviderFactory:
    def test_get_news_provider_default(self):
        provider = get_news_provider()
        assert isinstance(provider, FinnhubNewsProvider)

    def test_get_quote_provider_default(self):
        provider = get_quote_provider()
        assert isinstance(provider, FinnhubQuoteProvider)

    def test_get_ipo_provider_alpha_vantage(self):
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.ipo_provider = "alphavantage"
            provider = get_ipo_provider()
            assert isinstance(provider, AlphaVantageIPOProvider)

    def test_get_ipo_provider_finnhub(self):
        provider = get_ipo_provider("finnhub")
        assert isinstance(provider, FinnhubIPOProvider)

    def test_get_ipo_provider_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown IPO provider"):
            get_ipo_provider("nonexistent")


# ---------------------------------------------------------------------------
# FinnhubNewsProvider
# ---------------------------------------------------------------------------

class TestFinnhubNewsProvider:
    async def test_fetch_market_news_parses_response(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "id": 123,
                    "headline": "Market update",
                    "summary": "Stocks rally",
                    "source": "Reuters",
                    "url": "https://example.com/news",
                    "image": "https://example.com/img.jpg",
                    "category": "general",
                    "related": "AAPL,MSFT",
                    "datetime": 1700000000,
                }
            ],
        )
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/news")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubNewsProvider()
            articles = await provider.fetch_market_news()

        assert len(articles) == 1
        assert articles[0]["external_id"] == "finnhub-123"
        assert articles[0]["headline"] == "Market update"
        assert articles[0]["source"] == "Reuters"

    async def test_fetch_market_news_limits_to_50(self):
        items = [{"id": i, "headline": f"H{i}", "summary": "", "source": "",
                   "url": "", "image": "", "category": "general", "related": "",
                   "datetime": 1700000000 + i} for i in range(100)]
        mock_response = httpx.Response(200, json=items)
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/news")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubNewsProvider()
            articles = await provider.fetch_market_news()

        assert len(articles) == 50

    async def test_fetch_news_for_ticker(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "id": 456,
                    "headline": "AAPL earnings",
                    "summary": "Beat expectations",
                    "source": "CNBC",
                    "url": "https://example.com",
                    "image": "",
                    "datetime": 1700000000,
                }
            ],
        )
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/company-news")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubNewsProvider()
            articles = await provider.fetch_news_for_ticker("AAPL")

        assert len(articles) == 1
        assert articles[0]["related_tickers"] == "AAPL"
        assert articles[0]["category"] == "company"


# ---------------------------------------------------------------------------
# FinnhubQuoteProvider
# ---------------------------------------------------------------------------

class TestFinnhubQuoteProvider:
    async def test_fetch_quote_returns_price(self):
        mock_response = httpx.Response(
            200, json={"c": 200.5, "dp": 1.5, "h": 205, "l": 198, "o": 199, "pc": 197.5}
        )
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/quote")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubQuoteProvider()
            quote = await provider.fetch_quote("AAPL")

        assert quote["symbol"] == "AAPL"
        assert quote["price"] == 200.5
        assert quote["change_percent"] == 1.5

    async def test_fetch_quote_falls_back_to_yfinance_when_zero(self):
        mock_response = httpx.Response(200, json={"c": 0, "dp": 0})
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/quote")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
            patch(
                "app.providers.finnhub_provider._yfinance_quote",
                new_callable=AsyncMock,
                return_value={"symbol": "AAPL", "price": 150.0, "change_percent": 0.5},
            ),
        ):
            provider = FinnhubQuoteProvider()
            quote = await provider.fetch_quote("AAPL")

        assert quote["price"] == 150.0

    async def test_fetch_quotes_batch(self):
        responses = [
            httpx.Response(200, json={"c": 200, "dp": 1.0}),
            httpx.Response(200, json={"c": 400, "dp": -0.5}),
        ]
        for r in responses:
            r._request = httpx.Request("GET", "https://finnhub.io/api/v1/quote")

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            provider = FinnhubQuoteProvider()
            quotes = await provider.fetch_quotes_batch(["AAPL", "MSFT"])

        assert len(quotes) == 2
        assert quotes[0]["symbol"] == "AAPL"
        assert quotes[1]["symbol"] == "MSFT"


# ---------------------------------------------------------------------------
# FinnhubIPOProvider
# ---------------------------------------------------------------------------

class TestFinnhubIPOProvider:
    async def test_fetch_upcoming_ipos_parses_response(self):
        mock_response = httpx.Response(
            200,
            json={
                "ipoCalendar": [
                    {
                        "name": "TestCo Inc",
                        "symbol": "TEST",
                        "date": "2025-06-15",
                        "exchange": "NASDAQ",
                        "price": "10-15",
                        "numberOfShares": 5000000,
                        "status": "expected",
                    }
                ]
            },
        )
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/calendar/ipo")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert len(ipos) == 1
        assert ipos[0]["company_name"] == "TestCo Inc"
        assert ipos[0]["symbol"] == "TEST"
        assert ipos[0]["shares_offered"] == "5000000"

    async def test_fetch_upcoming_ipos_empty_calendar(self):
        mock_response = httpx.Response(200, json={"ipoCalendar": []})
        mock_response._request = httpx.Request("GET", "https://finnhub.io/api/v1/calendar/ipo")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            provider = FinnhubIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert ipos == []


# ---------------------------------------------------------------------------
# AlphaVantageIPOProvider
# ---------------------------------------------------------------------------

class TestAlphaVantageIPOProvider:
    async def test_fetch_upcoming_ipos_parses_csv(self):
        csv_data = (
            "symbol,name,ipoDate,priceRangeLow,priceRangeHigh,currency,exchange\n"
            "TEST,TestCo,2025-06-10,10,15,USD,NASDAQ\n"
            "TEST2,TestCo2,2025-06-20,20,25,USD,NYSE\n"
        )
        mock_response = httpx.Response(200, text=csv_data)
        mock_response._request = httpx.Request("GET", "https://www.alphavantage.co/query")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
            patch("app.providers.alpha_vantage_provider.settings") as mock_settings,
        ):
            mock_settings.alpha_vantage_api_key = "test-key"
            provider = AlphaVantageIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert len(ipos) == 2
        assert ipos[0]["symbol"] == "TEST"
        assert ipos[0]["price_range"] == "10-15"
        assert ipos[1]["company_name"] == "TestCo2"

    async def test_fetch_upcoming_ipos_filters_by_date(self):
        csv_data = (
            "symbol,name,ipoDate,priceRangeLow,priceRangeHigh,currency,exchange\n"
            "IN,InRange,2025-06-10,10,15,USD,NASDAQ\n"
            "OUT,OutRange,2025-08-01,20,25,USD,NYSE\n"
        )
        mock_response = httpx.Response(200, text=csv_data)
        mock_response._request = httpx.Request("GET", "https://www.alphavantage.co/query")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
            patch("app.providers.alpha_vantage_provider.settings") as mock_settings,
        ):
            mock_settings.alpha_vantage_api_key = "test-key"
            provider = AlphaVantageIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert len(ipos) == 1
        assert ipos[0]["symbol"] == "IN"

    async def test_fetch_upcoming_ipos_skips_bad_dates(self):
        csv_data = (
            "symbol,name,ipoDate,priceRangeLow,priceRangeHigh,currency,exchange\n"
            "BAD,BadCo,not-a-date,10,15,USD,NASDAQ\n"
            "GOOD,GoodCo,2025-06-15,20,25,USD,NYSE\n"
        )
        mock_response = httpx.Response(200, text=csv_data)
        mock_response._request = httpx.Request("GET", "https://www.alphavantage.co/query")

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
            patch("app.providers.alpha_vantage_provider.settings") as mock_settings,
        ):
            mock_settings.alpha_vantage_api_key = "test-key"
            provider = AlphaVantageIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert len(ipos) == 1
        assert ipos[0]["symbol"] == "GOOD"

    async def test_fetch_upcoming_ipos_returns_empty_when_no_key(self):
        with patch("app.providers.alpha_vantage_provider.settings") as mock_settings:
            mock_settings.alpha_vantage_api_key = ""
            provider = AlphaVantageIPOProvider()
            ipos = await provider.fetch_upcoming_ipos(
                datetime.date(2025, 6, 1), datetime.date(2025, 6, 30)
            )

        assert ipos == []
