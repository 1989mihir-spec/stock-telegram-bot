import os
import asyncio
from datetime import datetime

import yfinance as yf
from ta.momentum import RSIIndicator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN_US")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

WATCHLIST = [
    "NVDA",
    "MSFT",
    "AAPL",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "PLTR",
    "NFLX",
    "AVGO",
    "CRWD",
    "PANW",
    "ARM",
    "SNOW",
    "SHOP",
    "UBER",
    "COIN",
    "SMCI",
    "INTC"
]

def market_open():
    now = datetime.utcnow()

    if now.weekday() > 4:
        return False

    current = now.hour * 60 + now.minute

    # US market 13:30–20:00 UTC
    return 810 <= current <= 1200

async def send_message(msg):
    await bot.send_message(
        chat_id=CHAT_ID,
        text=msg
    )

async def scan():
    for stock in WATCHLIST:
        try:
            df = yf.download(
                stock,
                period="3mo",
                progress=False,
                auto_adjust=True
            )

            if len(df) < 50:
                continue

            close = df["Close"].squeeze()
            volume = df["Volume"].squeeze()

            price = float(close.iloc[-1])
            prev_price = float(close.iloc[-2])

            change_pct = ((price - prev_price) / prev_price) * 100

            if abs(change_pct) >= 1:
                direction = "📈 UP" if change_pct > 0 else "📉 DOWN"

                await send_message(
                    f"{direction} PRICE ALERT\n"
                    f"{stock}\n"
                    f"Price: ${price:.2f}\n"
                    f"Move: {change_pct:.2f}%"
                )

            rsi = RSIIndicator(close).rsi().iloc[-1]

            if rsi < 30:
                await send_message(
                    f"🟢 BUY WATCH\n"
                    f"{stock}\n"
                    f"Price: ${price:.2f}\n"
                    f"RSI: {rsi:.1f}"
                )

            elif rsi > 70:
                await send_message(
                    f"🔴 OVERBOUGHT\n"
                    f"{stock}\n"
                    f"Price: ${price:.2f}\n"
                    f"RSI: {rsi:.1f}"
                )

            ma20 = close.rolling(20).mean().iloc[-1]
            ma50 = close.rolling(50).mean().iloc[-1]

            if price > ma20 > ma50:
                await send_message(
                    f"📈 TREND ALERT\n"
                    f"{stock}\n"
                    f"Strong Uptrend"
                )

            avg_volume = volume.tail(20).mean()
            today_volume = volume.iloc[-1]

            if today_volume > avg_volume * 2:
                await send_message(
                    f"🚀 VOLUME BREAKOUT\n"
                    f"{stock}\n"
                    f"Volume {today_volume/avg_volume:.1f}x Average"
                )

        except Exception as e:
            print(stock, e)

async def main():
    await send_message(
        "🇺🇸 US Stock Bot Started - Monitoring 20 Stocks"
    )

    while True:
        try:
            if market_open():
                await scan()

            await asyncio.sleep(300)  # 5 minutes

        except Exception as e:
            print(e)
            await asyncio.sleep(60)

asyncio.run(main())