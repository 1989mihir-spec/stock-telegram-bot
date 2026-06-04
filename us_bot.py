import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf
from ta.momentum import RSIIndicator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN_US")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN_US and CHAT_ID must be set")

bot = Bot(token=BOT_TOKEN)

US_TZ = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

WATCHLIST = os.getenv(
    "WATCHLIST_US",
    "NVDA,MSFT,AAPL,AMZN,META,GOOGL,TSLA,AMD,PLTR,NFLX,AVGO,CRWD,PANW,ARM,SNOW,SHOP,UBER,COIN,SMCI,INTC"
).split(",")

sent_alerts = {}
last_summary_date = None


def market_open():
    now = datetime.now(US_TZ)

    if now.weekday() > 4:
        return False

    current = now.hour * 60 + now.minute
    return 570 <= current <= 960  # 9:30 AM - 4:00 PM ET


def already_sent(stock, alert_type):
    today = datetime.now(US_TZ).date()
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
        return []

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

            change_pct = ((price - prev_close) / prev_close) * 100
            gap_percent = ((today_open - prev_close) / prev_close) * 100

            rsi = RSIIndicator(close).rsi().iloc[-1]

            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1])

            high20 = float(close.tail(20).max())

            avg_volume = volume.tail(20).mean()
            today_volume = volume.iloc[-1]

            summary.append(
                f"{stock}\n"
                f"${price:.2f} | "
                f"O:{today_open:.2f} | "
                f"PC:{prev_close:.2f} | "
                f"RSI:{rsi:.1f}"
            )

            if abs(change_pct) >= 1 and not already_sent(stock, "MOVE"):
                direction = "📈 UP" if change_pct > 0 else "📉 DOWN"

                await send_message(
                    f"""<b>{direction} PRICE ALERT</b>

<b>{stock}</b>

Price: ${price:.2f}
Open: ${today_open:.2f}
Prev Close: ${prev_close:.2f}

Move: {change_pct:.2f}%"""
                )

            if (
                price > ma20 > ma50
                and rsi > 55
                and not already_sent(stock, "TREND")
            ):
                await send_message(
                    f"""📈 <b>TREND ALERT</b>

<b>{stock}</b>

Price: ${price:.2f}
Open: ${today_open:.2f}
Prev Close: ${prev_close:.2f}

RSI: {rsi:.1f}"""
                )

            if (
                price >= high20
                and not already_sent(stock, "BREAKOUT")
            ):
                await send_message(
                    f"""🔥 <b>20D BREAKOUT</b>

<b>{stock}</b>

Price: ${price:.2f}

20 Day High:
${high20:.2f}"""
                )

            if (
                today_volume > avg_volume * 2
                and price > ma20
                and not already_sent(stock, "VOLUME")
            ):
                await send_message(
                    f"""🚀 <b>VOLUME BREAKOUT</b>

<b>{stock}</b>

Volume:
{today_volume / avg_volume:.1f}x average"""
                )

            if (
                rsi < 30
                and not already_sent(stock, "BUY")
            ):
                await send_message(
                    f"""🟢 <b>BUY WATCH</b>

<b>{stock}</b>

Price: ${price:.2f}
RSI: {rsi:.1f}"""
                )

            if (
                rsi > 70
                and not already_sent(stock, "SELL")
            ):
                await send_message(
                    f"""🔴 <b>OVERBOUGHT</b>

<b>{stock}</b>

Price: ${price:.2f}
RSI: {rsi:.1f}"""
                )

            if (
                gap_percent > 2
                and not already_sent(stock, "GAPUP")
            ):
                await send_message(
                    f"""🚀 <b>GAP UP</b>

<b>{stock}</b>

Open: ${today_open:.2f}
Prev Close: ${prev_close:.2f}

Gap: {gap_percent:.2f}%"""
                )

            if (
                gap_percent < -2
                and not already_sent(stock, "GAPDOWN")
            ):
                await send_message(
                    f"""🔻 <b>GAP DOWN</b>

<b>{stock}</b>

Open: ${today_open:.2f}
Prev Close: ${prev_close:.2f}

Gap: {gap_percent:.2f}%"""
                )

        except Exception as e:
            logging.error(f"{stock}: {e}")

    return summary


async def send_daily_summary(summary):
    global last_summary_date

    today = datetime.now(US_TZ).date()

    if last_summary_date == today:
        return

    await send_message(
        "🇺🇸 <b>US MARKET SUMMARY</b>\n\n"
        + "\n\n".join(summary)
    )

    last_summary_date = today


async def main():
    await send_message(
        f"🇺🇸 US Stock Bot Started - Monitoring {len(WATCHLIST)} Stocks"
    )

    while True:
        try:
            now = datetime.now(US_TZ)

            summary = []

            if market_open():
                summary = await scan()

            if (
                now.hour == 16
                and now.minute >= 5
                and summary
            ):
                await send_daily_summary(summary)

            await asyncio.sleep(300)

        except Exception as e:
            logging.error(e)
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
