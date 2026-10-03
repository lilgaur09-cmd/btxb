# TRADEXBOT

TRADEXBOT is a Coinbase-powered live crypto analysis web app. The Vercel-ready Next.js app is in `web/`; the older Python/Streamlit prototype remains in the repository for reference and is not used by Vercel.

## BINARYTXBOT

BINARYTXBOT is the fixed-time binary-options signal giver built on the same
Coinbase-powered indicator engine as TRADEXBOT. Instead of spot Buy/Sell calls it
emits **CALL** (price above entry at expiry), **PUT** (price below entry at expiry),
or **NO TRADE** when fewer than 4 of its 7 factors agree.

- 7-factor directional confluence: EMA 9/21, EMA 21/50, MACD, RSI, stochastic, candle momentum, +DI/-DI
- Candlestick pattern detection: engulfing, hammer, shooting star, doji, marubozu
- Suggested expiry (1/3/5/15 minutes) matched to ATR%, ADX, and an expected-move estimate
- Confidence and quality labels that explain agreement (not a win rate)
- Sign-in-gated explainable assistant for signal, expiry, patterns, and risk questions

Run it locally (uses port 8502 so it can run beside TRADEXBOT):

```powershell
python -m streamlit run binarytxbot_app.py
```

Or launch it through the wrapper:

```powershell
python binarytxbot_launcher.py
```

Import the engine directly:

```python
from binary_analysis import fetch_binary_market, summarize_binary_market

candles, price = fetch_binary_market("BTC-USD", interval="1m", limit=180)
signal = summarize_binary_market("BTC-USD", candles, live_price=price, interval="1m")
print(signal["signal"], signal["expiry_minutes"], signal["confidence"])
```

Binary signals are informational only. They cannot guarantee a profitable expiry;
broker payouts are set by the broker.

## Deploy to Vercel

1. Import this repository into Vercel.
2. Set **Root Directory** to `web`.
3. Add `DATABASE_URL` for a Neon Postgres database and `SESSION_SECRET` (at least 32 random characters) in Project Settings → Environment Variables. These enable persistent AI-assistant accounts; charts and signals work without them.
4. Deploy using the Next.js preset and default build command.

Coinbase public market data does not require an API key. Candle history loads from REST and active candles stream from Coinbase WebSocket.

## Run locally

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. Copy `web/.env.example` to `web/.env.local` and fill in the Neon connection string and a strong session secret to test sign-in locally.

## Features

- Public live Coinbase candles, price, and technical signals
- Trade-by-trade candle updates without page refresh
- EMA, RSI, MACD, ATR, Bollinger bands, volume, and ADX context
- Sign-in-gated market assistant with explainable signal factors
- Persistent email/password accounts stored as salted PBKDF2 hashes in Neon Postgres

The assistant is deterministic indicator-based analysis, not a hosted generative language model. Signals are informational and cannot guarantee trading results.
