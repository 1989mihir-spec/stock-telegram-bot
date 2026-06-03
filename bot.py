import os
import asyncio
from datetime import datetime
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

WATCHLIST = [
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

def market_open():
    now = datetime.now()
    if now.weekday() > 4:
        return False

    current = now.hour * 60 + now.minute
    return 555 <= current <= 930  # 9:15 to 15:30

async def send_message(msg):
    await bot.send_message(chat_id=CHAT_ID, text=msg)

async def scan():
    for stock in WATCHLIST:
        try:
            df = yf.download(
                stock,
                period="3mo",
                progress=False,
                auto_adjust=True
            )

            if len(df) < 30:
                continue

            close = df["Close"].squeeze()

            rsi = RSIIndicator(close).rsi().iloc[-1]
            price = float(close.iloc[-1])
ma20 = close.rolling(20).mean().iloc[-1]
ma50 = close.rolling(50).mean().iloc[-1]

if price > ma20 > ma50:
    await send_message(
        f"📈 TREND ALERT\n{stock}\nStrong Uptrend"
    )
volume = df["Volume"].squeeze()

avg_volume = volume.tail(20).mean()
today_volume = volume.iloc[-1]

if today_volume > avg_volume * 2:
    await send_message(
        f"🚀 VOLUME BREAKOUT\n{stock}\nVolume {today_volume/avg_volume:.1f}x Average"
    )

            if rsi < 30:
                await send_message(
                    f"🟢 BUY WATCH\n{stock}\nPrice: ₹{price:.2f}\nRSI: {rsi:.1f}"
                )

            elif rsi > 70:
                await send_message(
                    f"🔴 PROFIT BOOKING WATCH\n{stock}\nPrice: ₹{price:.2f}\nRSI: {rsi:.1f}"
                )

        except Exception as e:
            print(stock, e)

async def main():
    await send_message("✅ Stock bot started successfully")
    while True:
        try:
            if market_open():
                await scan()

            await asyncio.sleep(900)  # 15 min
        except Exception as e:
            print(e)
            await asyncio.sleep(60)

asyncio.run(main())
