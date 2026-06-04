import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf
from ta.momentum import RSIIndicator
from telegram import Bot

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = ZoneInfo("Asia/Kolkata")

bot = Bot(token=BOT_TOKEN)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========================
# YOUR 9 STOCKS
# =========================

MY_STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "SBIN.NS",
    "BEL.NS",
    "TATAPOWER.NS",
    "TATASTEEL.NS",
    "JIOFIN.NS",
    "EQUITASBNK.NS"
]

# =========================
# NIFTY 50
# =========================

NIFTY50 = [
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "APOLLOHOSP.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS",
    "BAJAJFINSV.NS",
    "BEL.NS",
    "BHARTIARTL.NS",
    "CIPLA.NS",
    "COALINDIA.NS",
    "DRREDDY.NS",
    "EICHERMOT.NS",
    "ETERNAL.NS",
    "GRASIM.NS",
    "HCLTECH.NS",
    "HDFCBANK.NS",
    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",
    "HINDALCO.NS",
    "HINDUNILVR.NS",
    "ICICIBANK.NS",
    "INDUSINDBK.NS",
    "INFY.NS",
    "ITC.NS",
    "JIOFIN.NS",
    "JSWSTEEL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "M&M.NS",
    "MARUTI.NS",
    "NESTLEIND.NS",
    "NTPC.NS",
    "ONGC.NS",
    "POWERGRID.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",
    "SBIN.NS",
    "SHRIRAMFIN.NS",
    "SUNPHARMA.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "TCS.NS",
    "TECHM.NS",
    "TITAN.NS",
    "TRENT.NS",
    "ULTRACEMCO.NS",
    "WIPRO.NS"
]

WATCHLIST = sorted(list(set(MY_STOCKS + NIFTY50)))

sent_alerts = {}
last_summary_date = None


# =========================
# HELPERS
# =========================

def market_open():
    now = datetime.now(IST)

    if now.weekday() > 4:
        return False

    current = now.hour * 60 + now.minute

    return 555 <= current <= 930  # 9:15 AM to 3:30 PM


def already_sent(stock, alert_type):
    today = datetime.now(IST).date()

    key = f"{stock}_{alert_type}"

    if sent_alerts.get(key) == today:
        return True

    sent_alerts[key] = today
    return False


async def send_message(msg):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(e)


# =========================
# SCANNER
# =========================

async def scan():

    summary = []

    try:

        data = yf.download(
            WATCHLIST,
            period="3mo",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )

    except Exception as e:
        logging.error(f"Download error: {e}")
        return

    for stock in WATCHLIST:

        try:

            if stock not in data:
                continue

            df = data[stock].copy()

            if len(df) < 50:
                continue

            close = df["Close"].squeeze()
            volume = df["Volume"].squeeze()

            price = float(close.iloc[-1])

            today_open = float(df["Open"].iloc[-1])

            prev_close = float(close.iloc[-2])

            gap_percent = (
                (today_open - prev_close)
                / prev_close
            ) * 100

            rsi = RSIIndicator(close).rsi().iloc[-1]

            ma20 = float(
                close.rolling(20).mean().iloc[-1]
            )

            ma50 = float(
                close.rolling(50).mean().iloc[-1]
            )

            high20 = float(
                close.tail(20).max()
            )

            avg_volume = volume.tail(20).mean()
            today_volume = volume.iloc[-1]

            # =====================
            # SUMMARY
            # =====================

            summary.append(
                f"{stock}\n"
                f"₹{price:.2f} | "
                f"O:{today_open:.2f} | "
                f"PC:{prev_close:.2f} | "
                f"RSI:{rsi:.1f}"
            )

            # =====================
            # TREND ALERT
            # =====================

            if (
                price > ma20 > ma50
                and rsi > 55
                and not already_sent(stock, "TREND")
            ):

                await send_message(
                    f"""
📈 <b>TREND ALERT</b>

<b>{stock}</b>

Price: ₹{price:.2f}
Open: ₹{today_open:.2f}
Prev Close: ₹{prev_close:.2f}

RSI: {rsi:.1f}
"""
                )

            # =====================
            # BREAKOUT
            # =====================

            if (
                price >= high20
                and not already_sent(stock, "BREAKOUT")
            ):

                await send_message(
                    f"""
🔥 <b>20D BREAKOUT</b>

<b>{stock}</b>

Price: ₹{price:.2f}

20 Day High:
₹{high20:.2f}
"""
                )

            # =====================
            # VOLUME BREAKOUT
            # =====================

            if (
                today_volume > avg_volume * 2
                and price > ma20
                and not already_sent(stock, "VOLUME")
            ):

                await send_message(
                    f"""
🚀 <b>VOLUME BREAKOUT</b>

<b>{stock}</b>

Volume:
{today_volume / avg_volume:.1f}x
average
"""
                )

            # =====================
            # RSI BUY
            # =====================

            if (
                rsi < 30
                and not already_sent(stock, "BUY")
            ):

                await send_message(
                    f"""
🟢 <b>BUY WATCH</b>

<b>{stock}</b>

Price: ₹{price:.2f}
RSI: {rsi:.1f}
"""
                )

            # =====================
            # RSI SELL
            # =====================

            if (
                rsi > 70
                and not already_sent(stock, "SELL")
            ):

                await send_message(
                    f"""
🔴 <b>PROFIT BOOKING WATCH</b>

<b>{stock}</b>

Price: ₹{price:.2f}
RSI: {rsi:.1f}
"""
                )

            # =====================
            # GAP UP
            # =====================

            if (
                gap_percent > 2
                and not already_sent(stock, "GAPUP")
            ):

                await send_message(
                    f"""
🚀 <b>GAP UP</b>

<b>{stock}</b>

Open: ₹{today_open:.2f}
Prev Close: ₹{prev_close:.2f}

Gap:
{gap_percent:.2f}%
"""
                )

            # =====================
            # GAP DOWN
            # =====================

            if (
                gap_percent < -2
                and not already_sent(stock, "GAPDOWN")
            ):

                await send_message(
                    f"""
🔻 <b>GAP DOWN</b>

<b>{stock}</b>

Open: ₹{today_open:.2f}
Prev Close: ₹{prev_close:.2f}

Gap:
{gap_percent:.2f}%
"""
                )

        except Exception as e:
            logging.error(f"{stock}: {e}")

    return summary


# =========================
# DAILY SUMMARY
# =========================

async def send_daily_summary(summary):

    global last_summary_date

    today = datetime.now(IST).date()

    if last_summary_date == today:
        return

    await send_message(
        "📋 <b>NIFTY50 + WATCHLIST SUMMARY</b>\n\n"
        + "\n\n".join(summary[:50])
    )

    last_summary_date = today


# =========================
# MAIN
# =========================

async def main():

    await send_message(
        "✅ Stock Bot Started\n"
        "Tracking NIFTY50 + Custom Watchlist"
    )

    while True:

        try:

            now = datetime.now(IST)

            summary = await scan()

            # Daily summary at 3:35 PM
            if (
                now.hour == 15
                and now.minute >= 35
                and summary
            ):
                await send_daily_summary(summary)

            await asyncio.sleep(900)

        except Exception as e:

            logging.error(e)

            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())