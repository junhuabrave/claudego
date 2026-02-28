"""Chat service for ticker management via natural language."""

import re


def parse_chat_message(message: str) -> dict:
    """Parse user chat message and determine intent.

    Returns dict with keys: action, ticker, reply
    Supported intents:
      - add <TICKER>
      - remove/delete <TICKER>
      - list (show current watchlist)
      - help
      - general question (no action)
    """
    text = message.strip().lower()

    # Add ticker
    add_match = re.match(r"(?:add|watch|track|follow)\s+([a-zA-Z]{1,10})", text, re.IGNORECASE)
    if add_match:
        ticker = add_match.group(1).upper()
        return {
            "action": "add_ticker",
            "ticker": ticker,
            "reply": f"Adding {ticker} to your watchlist.",
        }

    # Remove ticker
    remove_match = re.match(
        r"(?:remove|delete|unwatch|untrack|unfollow|drop)\s+([a-zA-Z]{1,10})",
        text,
        re.IGNORECASE,
    )
    if remove_match:
        ticker = remove_match.group(1).upper()
        return {
            "action": "remove_ticker",
            "ticker": ticker,
            "reply": f"Removing {ticker} from your watchlist.",
        }

    # List watchlist
    if text in ("list", "watchlist", "show", "tickers", "my tickers"):
        return {
            "action": "list_tickers",
            "ticker": None,
            "reply": "Here is your current watchlist.",
        }

    # Help
    if text in ("help", "?", "commands"):
        return {
            "action": None,
            "ticker": None,
            "reply": (
                "Available commands:\n"
                "- **add TICKER** - Add a ticker to your watchlist\n"
                "- **remove TICKER** - Remove a ticker from your watchlist\n"
                "- **list** - Show your current watchlist\n"
                "- **help** - Show this help message"
            ),
        }

    return {
        "action": None,
        "ticker": None,
        "reply": (
            "I didn't understand that. Try 'add AAPL', 'remove TSLA', or 'list'. "
            "Type 'help' for all commands."
        ),
    }
