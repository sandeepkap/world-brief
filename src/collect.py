"""
collect.py — Pulls raw data from free/public sources.

Each function is defensive: a single source failing must never kill the run.
All functions return a short string block; missing data returns a clear marker
so the LLM knows a source was unavailable rather than hallucinating around it.
"""

import os
import time
import datetime as dt
import requests

TIMEOUT = 20


def _get(url, retries=3, backoff=4, **kwargs):
    """GET with simple retry on transient errors (429, 5xx)."""
    last = None
    for i in range(retries):
        r = requests.get(url, timeout=TIMEOUT, **kwargs)
        if r.status_code in (429, 500, 502, 503, 504):
            last = r
            time.sleep(backoff * (i + 1))
            continue
        return r
    return last  # caller's raise_for_status will surface the final failure


def _safe(fn, label):
    try:
        return fn()
    except Exception as e:
        return f"[{label}] UNAVAILABLE this run ({type(e).__name__}: {e})"


# ---------------------------------------------------------------------------
# Macro: FRED (Federal Reserve Economic Data). Free key from fredaccount.stlouisfed.org
# Pulls latest observation for key series.
# ---------------------------------------------------------------------------
def fred():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return "[macro/FRED] No FRED_API_KEY set — skipped."
    series = {
        "FEDFUNDS": "Fed Funds Rate",
        "CPIAUCSL": "CPI (all urban)",
        "UNRATE": "Unemployment Rate",
        "DGS10": "10Y Treasury Yield",
        "T10Y2Y": "10Y-2Y Spread",
    }
    out = ["[macro/FRED] Latest readings:"]
    for sid, name in series.items():
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": sid, "api_key": key, "file_type": "json",
            "sort_order": "desc", "limit": 1,
        }
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        obs = r.json()["observations"][0]
        out.append(f"  - {name}: {obs['value']} (as of {obs['date']})")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Markets: yfinance — delayed quotes, no key needed.
# ---------------------------------------------------------------------------
def markets():
    import yfinance as yf
    tickers = {
        "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^VIX": "VIX (fear index)",
        "DX-Y.NYB": "US Dollar Index", "GC=F": "Gold", "CL=F": "WTI Crude",
        "BTC-USD": "Bitcoin", "^TNX": "10Y Yield",
    }
    out = ["[markets] Last close / latest (delayed):"]
    data = yf.download(list(tickers.keys()), period="5d",
                       progress=False, group_by="ticker")
    for sym, name in tickers.items():
        try:
            closes = data[sym]["Close"].dropna()
            last, prev = closes.iloc[-1], closes.iloc[-2]
            pct = (last - prev) / prev * 100
            out.append(f"  - {name}: {last:,.2f} ({pct:+.2f}% vs prior)")
        except Exception:
            out.append(f"  - {name}: unavailable")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Watchlist: per-stock detail for tickers you care about.
# Reads tickers from the WATCHLIST env var (comma-separated). Falls back to a
# default set. yfinance gives delayed price + basic fundamentals, free.
# ---------------------------------------------------------------------------
DEFAULT_WATCHLIST = "NVDA,GOOGL,INTC,TTWO,META,AMZN,MSFT,PLTR,AAPL,TSLA,AMD,AVGO"


def watchlist():
    import yfinance as yf
    raw = os.environ.get("WATCHLIST", DEFAULT_WATCHLIST)
    syms = [s.strip().upper() for s in raw.split(",") if s.strip()]
    out = ["[watchlist] Per-stock snapshot (delayed price + fundamentals):"]
    for sym in syms:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            pct = (last - prev) / prev * 100
            info = t.info or {}
            pe = info.get("trailingPE")
            mcap = info.get("marketCap")
            hi52 = info.get("fiftyTwoWeekHigh")
            lo52 = info.get("fiftyTwoWeekLow")
            mcap_s = f"${mcap/1e9:,.0f}B" if mcap else "n/a"
            pe_s = f"{pe:.1f}" if pe else "n/a"
            rng = (f"{lo52:,.0f}-{hi52:,.0f}" if hi52 and lo52 else "n/a")
            out.append(
                f"  - {sym}: {last:,.2f} ({pct:+.2f}%) | P/E {pe_s} | "
                f"mcap {mcap_s} | 52wk {rng}"
            )
        except Exception as e:
            out.append(f"  - {sym}: unavailable ({type(e).__name__})")
    return "\n".join(out)
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "(economy OR markets OR Federal Reserve OR geopolitics) sourcelang:english",
        "mode": "artlist", "maxrecords": 20, "format": "json",
        "sort": "datedesc",
    }
    r = _get(url, params=params)
    r.raise_for_status()
    arts = r.json().get("articles", [])
    out = ["[news/GDELT] Recent headlines (last few hours):"]
    seen = set()
    for a in arts:
        title = a.get("title", "").strip()
        if title and title not in seen:
            seen.add(title)
            out.append(f"  - {title} ({a.get('domain','?')})")
    return "\n".join(out[:16])


# ---------------------------------------------------------------------------
# Economic calendar: scheduled future events worth knowing about.
# Free, no key: ForexFactory weekly calendar JSON. Lists this week's events
# with impact ratings; we surface the upcoming High/Medium ones.
# ---------------------------------------------------------------------------
def calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {"User-Agent": "Mozilla/5.0 (world-brief macro bot)"}
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    events = r.json()
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = []
    for e in events:
        if e.get("impact") not in ("High", "Medium"):
            continue
        # event date is ISO with offset, e.g. 2026-06-05T12:30:00-04:00
        try:
            when = dt.datetime.fromisoformat(e["date"])
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        if when >= now:
            upcoming.append((when, e))
    upcoming.sort(key=lambda x: x[0])
    out = ["[calendar] Upcoming High/Medium-impact events this week (UTC):"]
    for when, e in upcoming[:20]:
        stamp = when.astimezone(dt.timezone.utc).strftime("%a %m-%d %H:%M")
        out.append(f"  - {stamp} [{e.get('impact')}] {e.get('country')}: {e.get('title')}")
    return "\n".join(out) if upcoming else "[calendar] No upcoming high/medium events left this week."


def gather():
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks = [
        f"=== RAW DATA SNAPSHOT @ {now} ===",
        _safe(markets, "markets"),
        _safe(watchlist, "watchlist"),
        _safe(fred, "macro/FRED"),
        _safe(calendar, "calendar"),
        _safe(news, "news/GDELT"),
    ]
    return "\n\n".join(blocks)


if __name__ == "__main__":
    print(gather())