import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
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

WATCHLIST = [s.strip().upper() for s in os.getenv(
    "WATCHLIST_US",
    "NVDA,MSFT,AAPL,AMZN,META,GOOGL,TSLA,AMD,PLTR,NFLX,AVGO,CRWD,PANW,ARM,SNOW,SHOP,UBER,COIN,SMCI,INTC"
).split(",")]

sent_alerts = {}
last_summary_date = None
last_scan_summary = []
last_heartbeat_hour = None


def market_open():
    now = datetime.now(US_TZ)
    if now.weekday() > 4:
        return False
    current = now.hour * 60 + now.minute
    return 570 <= current <= 960


def already_sent(stock, alert_type):
    key = f"{stock}_{alert_type}"
    return sent_alerts.get(key) == datetime.now(US_TZ).date()


def mark_sent(stock, alert_type):
    sent_alerts[f"{stock}_{alert_type}"] = datetime.now(US_TZ).date()


async def send_message(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
        return True
    except Exception:
        logging.exception("Telegram send failed")
        return False


async def send_alert(stock, alert_type, message):
    if already_sent(stock, alert_type):
        return
    if await send_message(message):
        mark_sent(stock, alert_type)


async def scan():
    summary = []

    try:
        logging.info("Downloading market data...")
        data = yf.download(
            WATCHLIST,
            period="6mo",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception:
        logging.exception("Download error")
        return []

    if data.empty:
        logging.warning("No data returned from Yahoo Finance")
        return []

    ticker_levels = (
        data.columns.get_level_values(0)
        if hasattr(data.columns, "levels")
        else []
    )

    for stock in WATCHLIST:
        try:
            if stock not in ticker_levels:
                logging.warning("No data for %s", stock)
                continue

            df = data[stock].copy().dropna()

            if len(df) < 60:
                continue

            close = df["Close"]
            volume = df["Volume"]

            price = float(close.iloc[-1])
            today_open = float(df["Open"].iloc[-1])
            prev_close = float(close.iloc[-2])

            rsi = RSIIndicator(close).rsi().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma50 = close.rolling(50).mean().iloc[-1]

            if pd.isna(rsi) or pd.isna(ma20) or pd.isna(ma50):
                continue

            high20 = float(close.iloc[-21:-1].max())
            avg_volume = float(volume.tail(20).mean())
            today_volume = float(volume.iloc[-1])

            change_pct = ((price - prev_close) / prev_close) * 100
            gap_percent = ((today_open - prev_close) / prev_close) * 100

            summary.append(
                f"{stock}\n${price:.2f} | O:{today_open:.2f} | PC:{prev_close:.2f} | RSI:{rsi:.1f}"
            )

            if abs(change_pct) >= 1:
                direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
                await send_alert(
                    stock,
                    "MOVE",
                    f"<b>{direction} PRICE ALERT</b>\n\n<b>{stock}</b>\n\nMove: {change_pct:.2f}%\nPrice: ${price:.2f}",
                )

            if price > ma20 > ma50 and rsi > 55:
                await send_alert(
                    stock, "TREND",
                    f"📈 <b>TREND ALERT</b>\n\n<b>{stock}</b>\nPrice: ${price:.2f}\nRSI: {rsi:.1f}"
                )

            if price > high20:
                await send_alert(
                    stock, "BREAKOUT",
                    f"🔥 <b>20D BREAKOUT</b>\n\n<b>{stock}</b>\nPrice: ${price:.2f}\nPrior 20D High: ${high20:.2f}"
                )

            if avg_volume > 0 and today_volume > avg_volume * 2 and price > ma20:
                await send_alert(
                    stock, "VOLUME",
                    f"🚀 <b>VOLUME BREAKOUT</b>\n\n<b>{stock}</b>\nVolume: {today_volume / avg_volume:.1f}x average"
                )

            if rsi < 30:
                await send_alert(
                    stock, "BUY",
                    f"🟢 <b>BUY WATCH</b>\n\n<b>{stock}</b>\nPrice: ${price:.2f}\nRSI: {rsi:.1f}"
                )

            if rsi > 70:
                await send_alert(
                    stock, "SELL",
                    f"🔴 <b>OVERBOUGHT</b>\n\n<b>{stock}</b>\nPrice: ${price:.2f}\nRSI: {rsi:.1f}"
                )

            if gap_percent > 2:
                await send_alert(
                    stock, "GAPUP",
                    f"🚀 <b>GAP UP</b>\n\n<b>{stock}</b>\nGap: {gap_percent:.2f}%"
                )

            if gap_percent < -2:
                await send_alert(
                    stock, "GAPDOWN",
                    f"🔻 <b>GAP DOWN</b>\n\n<b>{stock}</b>\nGap: {gap_percent:.2f}%"
                )

        except Exception:
            logging.exception("Ticker processing failed: %s", stock)

    return summary


async def send_daily_summary(summary):
    global last_summary_date
    today = datetime.now(US_TZ).date()

    if last_summary_date == today or not summary:
        return

    if await send_message("🇺🇸 <b>US MARKET SUMMARY</b>\n\n" + "\n\n".join(summary)):
        last_summary_date = today


async def main():
    global last_scan_summary, last_heartbeat_hour

    now = datetime.now(US_TZ)

    await send_message(
        f"🇺🇸 US Stock Bot Started\nStocks: {len(WATCHLIST)}\nTime: {now.strftime('%Y-%m-%d %H:%M ET')}\nMarket Open: {market_open()}"
    )

    while True:
        try:
            now = datetime.now(US_TZ)

            if market_open():
                last_scan_summary = await scan()

            if now.hour == 16 and now.minute >= 5:
                await send_daily_summary(last_scan_summary)

            if now.minute == 0 and last_heartbeat_hour != now.hour:
                await send_message(
                    f"✅ Bot Alive\n{now.strftime('%Y-%m-%d %H:%M ET')}"
                )
                last_heartbeat_hour = now.hour

            await asyncio.sleep(300)

        except Exception:
            logging.exception("Main loop failure")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
