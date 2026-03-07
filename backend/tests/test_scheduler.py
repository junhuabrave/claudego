"""Test G — Background Scheduler Logic

Covers: poll_news, poll_ipos, poll_quotes, check_reminders.
All external providers and DB sessions are mocked.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import IPOEvent, PriceAlert, Reminder, Ticker, UserWatchlist
from app.services.scheduler import (
    check_price_alerts,
    check_reminders,
    poll_ipos,
    poll_news,
    poll_quotes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_async_session(execute_results=None):
    """Create a mock async session context manager.

    execute_results: list of return values for successive session.execute() calls.
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    if execute_results is not None:
        session.execute = AsyncMock(side_effect=execute_results)
    else:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

    return session


# ---------------------------------------------------------------------------
# poll_news
# ---------------------------------------------------------------------------

class TestPollNews:
    async def test_poll_news_skips_when_no_api_key(self):
        """When finnhub_api_key is empty, poll_news does nothing."""
        with patch("app.services.scheduler.settings") as mock_settings:
            mock_settings.finnhub_api_key = ""
            await poll_news()
            # No error, no DB call

    async def test_poll_news_fetches_and_stores_articles(self):
        mock_provider = AsyncMock()
        mock_provider.fetch_market_news.return_value = [
            {
                "external_id": "finnhub-123",
                "headline": "Market rally",
                "summary": "Stocks up",
                "source": "Reuters",
                "url": "https://example.com",
                "image_url": "",
                "category": "general",
                "related_tickers": "AAPL",
                "sentiment": "positive",
                "published_at": datetime.datetime.now(datetime.timezone.utc),
            }
        ]

        session = _mock_async_session()
        # Simulate pg_insert returning a new row id
        insert_result = MagicMock()
        insert_result.scalar_one_or_none.return_value = 1
        session.execute = AsyncMock(return_value=insert_result)

        broadcasts = []

        with (
            patch("app.services.scheduler.settings") as mock_settings,
            patch("app.services.scheduler.get_news_provider", return_value=mock_provider),
            patch("app.services.scheduler.async_session", return_value=session),
            patch(
                "app.services.scheduler.ws_manager.broadcast",
                side_effect=lambda t, d: broadcasts.append((t, d)),
            ),
        ):
            mock_settings.finnhub_api_key = "test-key"
            await poll_news()

        mock_provider.fetch_market_news.assert_awaited_once()
        assert len(broadcasts) == 1
        assert broadcasts[0][0] == "news"

    async def test_poll_news_handles_provider_error_gracefully(self):
        mock_provider = AsyncMock()
        mock_provider.fetch_market_news.side_effect = Exception("API timeout")

        with (
            patch("app.services.scheduler.settings") as mock_settings,
            patch("app.services.scheduler.get_news_provider", return_value=mock_provider),
        ):
            mock_settings.finnhub_api_key = "test-key"
            # Should not raise
            await poll_news()


# ---------------------------------------------------------------------------
# poll_ipos
# ---------------------------------------------------------------------------

class TestPollIpos:
    async def test_poll_ipos_fetches_and_broadcasts(self):
        mock_provider = AsyncMock()
        mock_provider.fetch_upcoming_ipos.return_value = [
            {
                "external_id": "av-ipo-TEST-2025-06-01",
                "company_name": "TestCo",
                "symbol": "TEST",
                "exchange": "NASDAQ",
                "price_range": "10-15",
                "shares_offered": "1000000",
                "expected_date": "2025-06-01",
                "status": "expected",
            }
        ]

        session = _mock_async_session()
        broadcasts = []

        with (
            patch("app.services.scheduler.get_ipo_provider", return_value=mock_provider),
            patch("app.services.scheduler.async_session", return_value=session),
            patch(
                "app.services.scheduler.ws_manager.broadcast",
                side_effect=lambda t, d: broadcasts.append((t, d)),
            ),
        ):
            await poll_ipos()

        mock_provider.fetch_upcoming_ipos.assert_awaited_once()
        assert len(broadcasts) == 1
        assert broadcasts[0][0] == "ipo_update"
        assert broadcasts[0][1]["count"] == 1

    async def test_poll_ipos_handles_error_gracefully(self):
        mock_provider = AsyncMock()
        mock_provider.fetch_upcoming_ipos.side_effect = Exception("Network error")

        with patch("app.services.scheduler.get_ipo_provider", return_value=mock_provider):
            await poll_ipos()


# ---------------------------------------------------------------------------
# poll_quotes
# ---------------------------------------------------------------------------

class TestPollQuotes:
    async def test_poll_quotes_skips_when_no_symbols(self):
        """No watched symbols → no provider call."""
        session = _mock_async_session()
        # fetchall returns empty list (no symbols)
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=result)

        with (
            patch("app.services.scheduler.async_session", return_value=session),
            patch("app.services.scheduler.settings") as mock_settings,
        ):
            mock_settings.finnhub_api_key = "test-key"
            await poll_quotes()

    async def test_poll_quotes_fetches_and_broadcasts(self):
        # First session call: get distinct symbols
        symbols_session = _mock_async_session()
        symbols_result = MagicMock()
        symbols_result.fetchall.return_value = [("AAPL",), ("MSFT",)]
        symbols_session.execute = AsyncMock(return_value=symbols_result)

        # Second session call: update ticker prices
        update_session = _mock_async_session()

        mock_provider = AsyncMock()
        mock_provider.fetch_quotes_batch.return_value = [
            {"symbol": "AAPL", "price": 200.0, "change_percent": 1.5},
            {"symbol": "MSFT", "price": 400.0, "change_percent": -0.5},
        ]

        broadcasts = []
        session_calls = [symbols_session, update_session]

        with (
            patch("app.services.scheduler.async_session", side_effect=session_calls),
            patch("app.services.scheduler.settings") as mock_settings,
            patch("app.services.scheduler.get_quote_provider", return_value=mock_provider),
            patch(
                "app.services.scheduler.ws_manager.broadcast",
                side_effect=lambda t, d: broadcasts.append((t, d)),
            ),
            patch("app.services.scheduler.check_price_alerts", new_callable=AsyncMock),
        ):
            mock_settings.finnhub_api_key = "test-key"
            await poll_quotes()

        mock_provider.fetch_quotes_batch.assert_awaited_once_with(["AAPL", "MSFT"])
        # Should broadcast quotes
        quote_broadcasts = [b for b in broadcasts if b[0] == "quotes"]
        assert len(quote_broadcasts) == 1

    async def test_poll_quotes_skips_when_no_api_key(self):
        session = _mock_async_session()
        result = MagicMock()
        result.fetchall.return_value = [("AAPL",)]
        session.execute = AsyncMock(return_value=result)

        with (
            patch("app.services.scheduler.async_session", return_value=session),
            patch("app.services.scheduler.settings") as mock_settings,
        ):
            mock_settings.finnhub_api_key = ""
            await poll_quotes()

    async def test_poll_quotes_handles_error_gracefully(self):
        session = _mock_async_session()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        with patch("app.services.scheduler.async_session", return_value=session):
            await poll_quotes()


# ---------------------------------------------------------------------------
# check_reminders
# ---------------------------------------------------------------------------

class TestCheckReminders:
    async def test_check_reminders_sends_due_reminder(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        tomorrow = now + datetime.timedelta(hours=12)
        ipo_date = tomorrow.date()

        reminder = MagicMock(spec=Reminder)
        reminder.id = 1
        reminder.sent = False
        reminder.remind_before_hours = 24
        reminder.notify_via = "email"
        reminder.notify_address = "test@example.com"

        ipo = MagicMock(spec=IPOEvent)
        ipo.expected_date = ipo_date
        ipo.company_name = "TestCo"
        ipo.symbol = "TEST"
        ipo.price_range = "10-15"
        ipo.exchange = "NASDAQ"

        session = _mock_async_session()
        result = MagicMock()
        result.fetchall.return_value = [(reminder, ipo)]
        session.execute = AsyncMock(return_value=result)

        with (
            patch("app.services.scheduler.async_session", return_value=session),
            patch("app.services.scheduler.send_reminder", new_callable=AsyncMock, return_value=True),
        ):
            await check_reminders()

    async def test_check_reminders_skips_already_sent(self):
        """Reminders with sent=True are filtered by the query."""
        session = _mock_async_session()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=result)

        with patch("app.services.scheduler.async_session", return_value=session):
            await check_reminders()

        session.execute.assert_awaited()

    async def test_check_reminders_handles_error_gracefully(self):
        session = _mock_async_session()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        with patch("app.services.scheduler.async_session", return_value=session):
            await check_reminders()
