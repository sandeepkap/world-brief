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

SYSTEM = """You are a macro-intelligence analyst writing a situational briefing.
You are given a raw data snapshot (markets, macro indicators, scheduled events,
news headlines). Produce a tight, structured briefing for a sophisticated reader.

Rules:
- Work ONLY from the data provided. If a source is marked UNAVAILABLE, say so;
  never invent numbers or events.
- Separate clearly: (1) WHAT CHANGED since a typical prior reading, (2) WHAT IT
  MAY MEAN (competing interpretations, not a single confident call), (3) WHAT'S
  SCHEDULED next that could move things.
- For each WATCHLIST stock, note what likely moved it today, where it sits in its
  52-week range, what its valuation (P/E) implies, and any stock-specific risk —
  but as observation, never a buy/sell call. If news in the snapshot relates to a
  ticker, connect it. Do not invent company news that isn't in the data.
- You are NOT giving buy/sell advice. Frame everything as situational awareness
  and risks to watch. Flag uncertainty honestly. Markets are not predictable.
- Be concise. No filler. Plain English."""

PROMPT_TMPL = """Today is {date}.

Here is the raw data snapshot:

{data}

Write the briefing now. Structure it as:
1. ONE-LINE SUMMARY
2. WHAT CHANGED (bullets)
3. WHAT IT MAY MEAN (2-4 short paragraphs, present competing reads)
4. WATCHLIST (one tight line per stock: move, range position, valuation read, key risk)
5. SCHEDULED AHEAD (bullets)
6. RISKS TO WATCH (bullets)
End with: "Research input only — not financial advice."
"""


def synthesize(data: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    today = dt.date.today().isoformat()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
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