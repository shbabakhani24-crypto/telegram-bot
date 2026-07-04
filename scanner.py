import ccxt
import pandas as pd

from indicators import rsi, ichimoku

exchange = ccxt.okx({"options": {"defaultType": "spot"}})


def get_symbols():
    return [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "DOGE/USDT"
    ]


def get_data(symbol, tf="4h", limit=120):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)

    df = pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])
    return df


def score(df):
    df["rsi"] = rsi(df["c"])
    df["ema_rsi"] = df["rsi"].ewm(span=9).mean()

    tenkan, kijun, span_a, span_b = ichimoku(df)

    price = df["c"].iloc[-1]
    rsi_val = df["rsi"].iloc[-1]
    ema_rsi = df["ema_rsi"].iloc[-1]

    vol = df["v"].iloc[-1] / df["v"].rolling(20).mean().iloc[-1]
    ma50 = df["c"].rolling(50).mean().iloc[-1]

    s = 0

    if price > ma50:
        s += 15

    if price > tenkan.iloc[-1]:
        s += 10

    if tenkan.iloc[-1] > kijun.iloc[-1]:
        s += 20

    if price > span_a.iloc[-1] and price > span_b.iloc[-1]:
        s += 15

    if rsi_val > 50:
        s += 10

    if rsi_val > ema_rsi:
        s += 10

    if vol > 1.5:
        s += 15

    return s, price, rsi_val, vol


def scan():
    symbols = get_symbols()

    results = []
    errors = []

    for sym in symbols:  # keep small for testing
        try:
            df = get_data(sym)
            s, price, rsi_val, vol = score(df)

            if s >= 75:
                results.append((sym, s, price, rsi_val, vol))

        except Exception as exc:
            errors.append(f"{sym}: {exc}")
            continue

    results.sort(key=lambda x: x[1], reverse=True)

    top = results[:5]

    if not top:
        if errors:
            return (
                "⚠️ Unable to fetch market data for the scan.\n"
                f"Errors: {'; '.join(errors[:3])}"
            )
        return "❌ No setups found."

    msg = "🚀 TOP ICHIMOKU SETUPS\n\n"

    for sym, s, price, rsi_val, vol in top:
        msg += (
            f"{sym}\n"
            f"Score: {s}\n"
            f"Price: {price}\n"
            f"RSI: {rsi_val:.2f}\n"
            f"Volume: {vol:.2f}x\n\n"
        )

    return msg