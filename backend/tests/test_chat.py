"""Test F — Chat Command Parsing (Unit Tests)

Covers: parse_chat_message() for all supported intents:
add, remove, list, help, and unknown input.
Tests the pure function directly — no HTTP, no DB.
"""

import pytest

from app.services.chat import parse_chat_message


# ---------------------------------------------------------------------------
# Add ticker
# ---------------------------------------------------------------------------

class TestAddTicker:
    def test_add_basic(self):
        result = parse_chat_message("add AAPL")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "AAPL"

    def test_add_lowercase(self):
        result = parse_chat_message("add aapl")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "AAPL"

    def test_add_with_watch_synonym(self):
        result = parse_chat_message("watch TSLA")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "TSLA"

    def test_add_with_track_synonym(self):
        result = parse_chat_message("track MSFT")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "MSFT"

    def test_add_with_follow_synonym(self):
        result = parse_chat_message("follow GOOG")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "GOOG"

    def test_add_international_symbol_with_caret(self):
        """Caret-prefixed symbols like ^KS11 should be accepted."""
        result = parse_chat_message("add ^KS11")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "^KS11"

    def test_add_symbol_with_dot(self):
        """Yahoo Finance symbols like VOD.L should parse."""
        result = parse_chat_message("add VOD.L")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "VOD.L"

    def test_add_with_leading_whitespace(self):
        result = parse_chat_message("  add AAPL")
        assert result["action"] == "add_ticker"
        assert result["ticker"] == "AAPL"

    def test_add_reply_mentions_ticker(self):
        result = parse_chat_message("add NVDA")
        assert "NVDA" in result["reply"]


# ---------------------------------------------------------------------------
# Remove ticker
# ---------------------------------------------------------------------------

class TestRemoveTicker:
    def test_remove_basic(self):
        result = parse_chat_message("remove AAPL")
        assert result["action"] == "remove_ticker"
        assert result["ticker"] == "AAPL"

    def test_delete_synonym(self):
        result = parse_chat_message("delete TSLA")
        assert result["action"] == "remove_ticker"
        assert result["ticker"] == "TSLA"

    def test_unwatch_synonym(self):
        result = parse_chat_message("unwatch MSFT")
        assert result["action"] == "remove_ticker"
        assert result["ticker"] == "MSFT"

    def test_untrack_synonym(self):
        result = parse_chat_message("untrack GOOG")
        assert result["action"] == "remove_ticker"

    def test_unfollow_synonym(self):
        result = parse_chat_message("unfollow META")
        assert result["action"] == "remove_ticker"

    def test_drop_synonym(self):
        result = parse_chat_message("drop AMZN")
        assert result["action"] == "remove_ticker"
        assert result["ticker"] == "AMZN"

    def test_remove_reply_mentions_ticker(self):
        result = parse_chat_message("remove NVDA")
        assert "NVDA" in result["reply"]


# ---------------------------------------------------------------------------
# List watchlist
# ---------------------------------------------------------------------------

class TestListWatchlist:
    def test_list_command(self):
        result = parse_chat_message("list")
        assert result["action"] == "list_tickers"
        assert result["ticker"] is None

    def test_watchlist_command(self):
        result = parse_chat_message("watchlist")
        assert result["action"] == "list_tickers"

    def test_show_command(self):
        result = parse_chat_message("show")
        assert result["action"] == "list_tickers"

    def test_tickers_command(self):
        result = parse_chat_message("tickers")
        assert result["action"] == "list_tickers"

    def test_my_tickers_command(self):
        result = parse_chat_message("my tickers")
        assert result["action"] == "list_tickers"


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

class TestHelp:
    def test_help_command(self):
        result = parse_chat_message("help")
        assert result["action"] is None
        assert "add" in result["reply"].lower()
        assert "remove" in result["reply"].lower()

    def test_question_mark_command(self):
        result = parse_chat_message("?")
        assert result["action"] is None
        assert "commands" in result["reply"].lower() or "add" in result["reply"].lower()

    def test_commands_command(self):
        result = parse_chat_message("commands")
        assert result["action"] is None


# ---------------------------------------------------------------------------
# Unknown input
# ---------------------------------------------------------------------------

class TestUnknownInput:
    def test_random_text(self):
        result = parse_chat_message("hello world")
        assert result["action"] is None
        assert result["ticker"] is None
        assert "help" in result["reply"].lower()

    def test_empty_after_strip(self):
        result = parse_chat_message("   ")
        assert result["action"] is None
        assert result["ticker"] is None

    def test_partial_add_no_ticker(self):
        """'add' with no ticker should not match the add pattern."""
        result = parse_chat_message("add")
        assert result["action"] is None

    def test_numeric_only(self):
        result = parse_chat_message("12345")
        assert result["action"] is None
