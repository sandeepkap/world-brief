"""
collect.py — Pulls raw data from free/public sources.

Each function is defensive: a single source failing must never kill the run.
All functions return a short string block; missing data returns a clear marker
so the LLM knows a source was unavailable rather than hallucinating around it.
"""

import os
import datetime as dt
import requests

TIMEOUT = 20


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
# News: GDELT — free global news, no key. Returns recent salient articles.
# ---------------------------------------------------------------------------
def news():
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "(economy OR markets OR Federal Reserve OR geopolitics) sourcelang:english",
        "mode": "artlist", "maxrecords": 20, "format": "json",
        "sort": "datedesc",
    }
    r = requests.get(url, params=params, timeout=TIMEOUT)
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
# Free source via Financial Modeling Prep (key) OR a static reminder fallback.
# ---------------------------------------------------------------------------
def calendar():
    key = os.environ.get("FMP_API_KEY")
    today = dt.date.today()
    end = today + dt.timedelta(days=7)
    if not key:
        return ("[calendar] No FMP_API_KEY set — skipped. "
                "Consider adding for forward-looking economic events.")
    url = "https://financialmodelingprep.com/api/v3/economic_calendar"
    params = {"from": str(today), "to": str(end), "apikey": key}
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    events = r.json()
    hi = [e for e in events if e.get("impact") == "High"][:15]
    out = ["[calendar] High-impact events next 7 days:"]
    for e in hi:
        out.append(f"  - {e.get('date')} {e.get('country')}: {e.get('event')}")
    return "\n".join(out) if hi else "[calendar] No high-impact events flagged."


def gather():
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks = [
        f"=== RAW DATA SNAPSHOT @ {now} ===",
        _safe(markets, "markets"),
        _safe(fred, "macro/FRED"),
        _safe(calendar, "calendar"),
        _safe(news, "news/GDELT"),
    ]
    return "\n\n".join(blocks)


if __name__ == "__main__":
    print(gather())
