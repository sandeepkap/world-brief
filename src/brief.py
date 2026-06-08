"""
brief.py — Takes the raw data snapshot, asks Claude to synthesize a structured
briefing, then emails it. Run by GitHub Actions on a schedule.
"""

import os
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import anthropic
from collect import gather

MODEL = "claude-sonnet-4-6"  # cost-efficient. For max capability, use claude-opus-4-8

SYSTEM = """You are a market analyst writing a plain-English briefing for one
person who is not a finance professional. Write like a smart friend explaining
things over coffee — clear, direct, no jargon. If you must use a term like P/E,
explain it in a few words.

You are given a raw data snapshot: market indices, a per-stock watchlist (price,
P/E, market cap, 52-week range), UNVERIFIED Reddit chatter, macro indicators,
scheduled events, and news headlines.

Rules:
- Work ONLY from the data provided. If a source is marked UNAVAILABLE, say so.
  Never invent numbers, company news, or events.
- For each watchlist stock, give: (a) a plain-English read of what's going on,
  (b) a LEAN — one of LEANS POSITIVE / MIXED / LEANS CAUTIOUS, and (c) a
  CONFIDENCE score 1-5 (1 = barely more than a guess, 5 = strong). Be honest:
  with only delayed price, basic fundamentals, and chatter, most confidence
  scores should be LOW (1-3). A high score must be genuinely justified.
- The lean is an opinion to weigh, NOT a recommendation to act. State plainly in
  the intro that these are leans, not buy/sell calls, that the data is thin
  (delayed prices, patchy fundamentals, unverified chatter), and that the reader
  decides. If a stock's data looks inconsistent or a big move has no explanation
  in the data, SAY the driver is unknown rather than guessing.
- Treat Reddit strictly as crowd mood. Never let it drive a lean on its own; note
  it as "the crowd is talking up/down X" and flag that it's unverified and pumpable.
- You are not a financial advisor and this is not financial advice. Markets are
  not predictable. Keep that honest throughout."""

PROMPT_TMPL = """Today is {date}.

Here is the raw data snapshot:

{data}

Write the briefing now in plain English. Structure it as:

1. THE GIST — 2-3 sentences: what kind of day it is and the one thing that matters most.

2. YOUR STOCKS — for EACH watchlist ticker, a short block like:
   **TICKER — LEANS [POSITIVE/MIXED/CAUTIOUS] · Confidence X/5**
   One or two sentences in plain English: what moved it, where it sits (cheap/
   expensive, near highs/lows in plain terms), what the crowd's saying if notable,
   and the main thing to weigh. No jargon dumps.

3. WHAT'S COMING — the scheduled events that could move your stocks, in plain terms
   (e.g. "Wednesday's inflation report could swing the whole market").

4. BOTTOM LINE — 2-3 sentences tying it together. Remind that these are leans on
   thin data, not buy/sell calls, and the decision is theirs.

End with: "These are AI leans on limited data, not financial advice. You decide."
"""


def synthesize(data: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    today = dt.date.today().isoformat()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": PROMPT_TMPL.format(date=today, data=data)}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def send_email(subject: str, body: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    pw = os.environ["SMTP_PASS"]
    to = os.environ["EMAIL_TO"]

    m = MIMEMultipart()
    m["From"], m["To"], m["Subject"] = user, to, subject
    m.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(m)


def main():
    data = gather()
    brief = synthesize(data)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"World Brief — {stamp}"
    full = f"{brief}\n\n---\n{data}"  # briefing first, raw data appended for audit
    if os.environ.get("EMAIL_TO"):
        send_email(subject, full)
        print("Email sent.")
    else:
        print(full)  # local dry-run: just print


if __name__ == "__main__":
    main()