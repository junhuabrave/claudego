"""Background scheduler for polling data providers and sending reminders."""

import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import async_session
from app.models.models import IPOEvent, NewsArticle, Reminder, Ticker
from app.providers.factory import get_ipo_provider, get_news_provider, get_quote_provider
from app.services.notification import send_reminder
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def poll_news():
    """Fetch latest market news and broadcast new articles."""
    try:
        provider = get_news_provider()
        articles = await provider.fetch_market_news()
        async with async_session() as session:
            for article in articles:
                stmt = (
                    pg_insert(NewsArticle)
                    .values(**article)
                    .on_conflict_do_nothing(index_elements=["external_id"])
                    .returning(NewsArticle.id)
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row is not None:
                    await ws_manager.broadcast("news", article)
            await session.commit()
        logger.info("Polled %d news articles", len(articles))
    except Exception:
        logger.exception("Error polling news")


async def poll_ipos():
    """Fetch upcoming IPO events for the next 2 weeks."""
    try:
        provider = get_ipo_provider()
        today = datetime.date.today()
        two_weeks = today + datetime.timedelta(days=14)
        ipos = await provider.fetch_upcoming_ipos(today, two_weeks)
        async with async_session() as session:
            for ipo in ipos:
                stmt = (
                    pg_insert(IPOEvent)
                    .values(**ipo)
                    .on_conflict_do_nothing(index_elements=["external_id"])
                )
                await session.execute(stmt)
            await session.commit()
            await ws_manager.broadcast("ipo_update", {"count": len(ipos)})
        logger.info("Polled %d IPO events", len(ipos))
    except Exception:
        logger.exception("Error polling IPOs")


async def poll_quotes():
    """Fetch latest quotes for all active tickers."""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Ticker.symbol).where(Ticker.active.is_(True))
            )
            symbols = [row[0] for row in result.fetchall()]

        if not symbols:
            return

        provider = get_quote_provider()
        quotes = await provider.fetch_quotes_batch(symbols)

        async with async_session() as session:
            for q in quotes:
                if q["price"] is not None:
                    await session.execute(
                        update(Ticker)
                        .where(Ticker.symbol == q["symbol"])
                        .values(last_price=q["price"], change_percent=q["change_percent"])
                    )
            await session.commit()

        await ws_manager.broadcast("quotes", {"quotes": quotes})
        logger.info("Updated quotes for %d tickers", len(quotes))
    except Exception:
        logger.exception("Error polling quotes")


async def check_reminders():
    """Check for reminders that need to be sent."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with async_session() as session:
            result = await session.execute(
                select(Reminder, IPOEvent)
                .join(IPOEvent, Reminder.ipo_event_id == IPOEvent.id)
                .where(Reminder.sent.is_(False))
            )
            rows = result.fetchall()

            for reminder, ipo in rows:
                ipo_dt = datetime.datetime.combine(
                    ipo.expected_date, datetime.time(9, 30), tzinfo=datetime.timezone.utc
                )
                trigger_at = ipo_dt - datetime.timedelta(hours=reminder.remind_before_hours)
                if now >= trigger_at:
                    title = f"IPO Reminder: {ipo.company_name} ({ipo.symbol})"
                    body = (
                        f"<h3>{ipo.company_name} IPO</h3>"
                        f"<p>Expected date: {ipo.expected_date}</p>"
                        f"<p>Price range: {ipo.price_range}</p>"
                        f"<p>Exchange: {ipo.exchange}</p>"
                    )
                    success = await send_reminder(
                        reminder.notify_via, reminder.notify_address, title, body
                    )
                    if success:
                        await session.execute(
                            update(Reminder)
                            .where(Reminder.id == reminder.id)
                            .values(sent=True)
                        )
            await session.commit()
    except Exception:
        logger.exception("Error checking reminders")


def start_scheduler():
    scheduler.add_job(poll_news, "interval", seconds=settings.news_poll_interval_seconds, id="poll_news")
    scheduler.add_job(poll_ipos, "interval", seconds=settings.ipo_poll_interval_seconds, id="poll_ipos")
    scheduler.add_job(poll_quotes, "interval", seconds=settings.quotes_poll_interval_seconds, id="poll_quotes")
    scheduler.add_job(check_reminders, "interval", seconds=300, id="check_reminders")
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
