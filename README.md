# world-brief

Automated macro-intelligence briefing. Pulls markets / macro / news / scheduled
events, has Claude synthesize a structured situational briefing, and emails it to
you on a schedule (every 4 hours by default). Runs entirely on free GitHub Actions
minutes — no server to maintain, nothing needs to stay open.

> Research input only. This is situational awareness, not financial advice, and
> no system reliably predicts markets. Treat output as a fast organized read of
> what's happening, not a signal to act on.

## How it works

```
GitHub Actions cron (every 4h)
        │
        ▼
   collect.py ──> pulls markets (yfinance), macro (FRED),
        │         calendar (FMP), news (GDELT)
        ▼
    brief.py  ──> Claude synthesizes a structured briefing
        │
        ▼
     email   ──> lands in your inbox
```

## Setup (about 15 minutes)

1. **Create a new GitHub repo** and push these files into it.

2. **Get the keys you want** (all have free tiers; only Anthropic + email are required):
   - `ANTHROPIC_API_KEY` — required. console.anthropic.com
   - `FRED_API_KEY` — free, optional. fredaccount.stlouisfed.org → request API key
   - `FMP_API_KEY` — free tier, optional (forward calendar). financialmodelingprep.com
   - Email: easiest is a Gmail account with an **App Password** (not your normal
     password). Settings → SMTP_HOST=`smtp.gmail.com`, SMTP_PORT=`587`.

3. **Add them as repo secrets**: repo → Settings → Secrets and variables →
   Actions → New repository secret. Add each of:
   `ANTHROPIC_API_KEY`, `FRED_API_KEY`, `FMP_API_KEY`,
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`.

4. **Test it now**: repo → Actions tab → "world-brief" → "Run workflow". This runs
   immediately so you don't wait 4 hours to see if it works.

5. **It's now automatic.** The cron fires every 4 hours. Adjust the schedule by
   editing the `cron:` line in `.github/workflows/brief.yml`.

## Running locally (dry run, prints instead of emailing)

```bash
pip install -r requirements.txt
cd src
export ANTHROPIC_API_KEY=sk-...
export FRED_API_KEY=...        # optional
python brief.py                # no EMAIL_TO set → prints the briefing
```

## Notes / honest limits

- **GitHub cron is best-effort.** Under load it can run late or skip; for exact
  timing you'd move to a paid scheduler (cloud function + EventBridge/Cloud
  Scheduler). For a personal briefing, best-effort is fine.
- **Free data is delayed/limited.** yfinance is delayed quotes; real-time feeds
  cost money. Add paid sources later by writing new functions in `collect.py` —
  the architecture is built to extend, just append a block and add it to `gather()`.
- **Cost.** Each run is one Claude call (a few cents) plus free GitHub minutes.
  Every 4h = 6 runs/day. Swap `MODEL` in `brief.py` to a cheaper model to cut cost.
- **"Every single resource" isn't achievable** — terms of service, paywalls, and
  rate limits constrain what any system can legally and practically pull. This
  covers the high-value free sources and is designed so you bolt on more.
