"""Map user-facing ticker symbols (Yahoo Finance style) to Finnhub exchange format.

Finnhub uses  EXCHANGE:SYMBOL  for non-US stocks, e.g. LSE:VOD.
US stocks (no suffix) are passed through unchanged.

Exchange codes are sourced from Finnhub's supported-exchange list (MIC-based).
Confirmed codes: LSE, XPAR, XETR, XAMS, XBRU, XLIS, HKEX, TSE.
Remaining codes are best-effort — verify via GET /stock/symbol?exchange=<code>
if you add a new market.
"""

# Yahoo Finance dot-suffix → Finnhub exchange prefix
_SUFFIX_TO_FINNHUB: dict[str, str] = {
    # ── UK ───────────────────────────────────────────────────────────────────
    "L": "LSE",        # London Stock Exchange
    # ── Europe ───────────────────────────────────────────────────────────────
    "PA": "XPAR",      # Euronext Paris
    "DE": "XETR",      # XETRA (Deutsche Börse, Frankfurt)
    "F": "XFRA",       # Frankfurt Borse (different venue from XETRA)
    "MI": "XMIL",      # Borsa Italiana (Milan)
    "MC": "XMAD",      # Bolsa de Madrid
    "AS": "XAMS",      # Euronext Amsterdam
    "BR": "XBRU",      # Euronext Brussels
    "SW": "XSWX",      # SIX Swiss Exchange
    "ST": "XSTO",      # Nasdaq Stockholm
    "OL": "XOSL",      # Oslo Børs
    "HE": "XHEL",      # Nasdaq Helsinki
    "CO": "XCSE",      # Nasdaq Copenhagen
    "LS": "XLIS",      # Euronext Lisbon
    "VI": "XWBO",      # Wiener Börse (Vienna)
    "WA": "XWAR",      # Warsaw Stock Exchange
    "PR": "XPRA",      # Prague Stock Exchange
    "IS": "XIST",      # Borsa Istanbul
    "AT": "XATH",      # Athens Stock Exchange
    "BD": "XBUD",      # Budapest Stock Exchange
    "RO": "XBSE",      # Bucharest Stock Exchange
    # ── Asia-Pacific ─────────────────────────────────────────────────────────
    "HK": "HKEX",      # Hong Kong Exchanges and Clearing
    "T": "TSE",        # Tokyo Stock Exchange
    "SS": "XSHG",      # Shanghai Stock Exchange
    "SZ": "XSHE",      # Shenzhen Stock Exchange
    "SI": "SGX",       # Singapore Exchange
    "KS": "XKRX",      # Korea Stock Exchange
    "KQ": "XKOS",      # KOSDAQ
    "BO": "XBOM",      # BSE India (Bombay)
    "NS": "XNSE",      # NSE India (National)
    "TW": "XTAI",      # Taiwan Stock Exchange
    "TWO": "ROCO",     # Taipei Exchange (OTC)
    "AX": "XASX",      # Australian Securities Exchange
    "NZ": "XNZE",      # NZX (New Zealand)
    "BK": "XBKK",      # Stock Exchange of Thailand
    "JK": "XIDX",      # Indonesia Stock Exchange
    "KL": "XKLS",      # Bursa Malaysia
    # ── Americas ─────────────────────────────────────────────────────────────
    "TO": "XTSE",      # Toronto Stock Exchange (TSX)
    "V": "XTSX",       # TSX Venture Exchange
    "MX": "XMEX",      # Bolsa Mexicana de Valores
    "SA": "BVMF",      # B3 (Brazil — São Paulo)
    "BA": "XBUE",      # Buenos Aires Stock Exchange
    "SN": "XSGO",      # Santiago Stock Exchange (Chile)
    "LM": "XLIM",      # Lima Stock Exchange (Peru)
    # ── Africa & Middle East ─────────────────────────────────────────────────
    "JO": "XJSE",      # Johannesburg Stock Exchange
    "TA": "XTAE",      # Tel Aviv Stock Exchange
    "SR": "XSAU",      # Saudi Exchange (Tadawul)
    "DU": "XDFM",      # Dubai Financial Market
    "AD": "XADS",      # Abu Dhabi Securities Exchange
    "CA": "XCAI",      # Egyptian Exchange
}


def to_finnhub(symbol: str) -> str:
    """Return the Finnhub-format symbol for *symbol*.

    Rules
    -----
    - Already contains ':'  → assumed to be Finnhub format already, pass through.
    - Contains a trailing dot-suffix (e.g. VOD.L, BMW.DE) → convert to
      EXCHANGE:BASE using the lookup table.
    - No dot (e.g. AAPL, TSLA) → US stock, pass through unchanged.
    - Unknown suffix → pass through unchanged (Finnhub will return zeros,
      which is the same behaviour as today — no regression).

    Examples
    --------
    >>> to_finnhub("VOD.L")
    'LSE:VOD'
    >>> to_finnhub("BMW.DE")
    'XETR:BMW'
    >>> to_finnhub("AAPL")
    'AAPL'
    >>> to_finnhub("LSE:VOD")
    'LSE:VOD'
    """
    if ":" in symbol:
        return symbol  # already in Finnhub format

    if "." in symbol:
        base, suffix = symbol.rsplit(".", 1)
        exchange = _SUFFIX_TO_FINNHUB.get(suffix.upper())
        if exchange:
            return f"{exchange}:{base}"

    return symbol  # US stock or unrecognised — pass through
