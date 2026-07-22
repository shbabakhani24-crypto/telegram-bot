import ccxt
import pandas as pd

from indicators import ichimoku

exchange = ccxt.lbank({"options": {"defaultType": "spot"}})

symbols = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "TRX/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "UNI/USDT",
    "LTC/USDT",
    "XLM/USDT",
    "ALGO/USDT",
    "ATOM/USDT",
    "ARB/USDT",
    "OP/USDT",
    "TIA/USDT",
    "INJ/USDT",
    "SHIB/USDT",
    "DOT/USDT",
    "BCH/USDT",
    "ICP/USDT",
    "NEAR/USDT",
    "TON/USDT",
    "AAVE/USDT",
    "SUI/USDT",
    "PEPE/USDT",
    "FIL/USDT",
    "RUNE/USDT",
    "ETC/USDT",
    "XMR/USDT",
    "EOS/USDT",
    "HBAR/USDT",
    "KAS/USDT",
    "VET/USDT",
    "FLOW/USDT",
    "APT/USDT",
    "SEI/USDT",
    "RNDR/USDT",
    "IMX/USDT",
    "ONDO/USDT",
    "TAO/USDT",
    "FET/USDT",
    "GRT/USDT",
    "MATIC/USDT",
    "WIF/USDT",
    "SAND/USDT",
    "JUP/USDT",
    "BLUR/USDT",
]


def get_data(symbol, tf="4h"):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=200)
    return pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])


def prepare_indicators(df):
    df = df.copy()

    tenkan, kijun, span_a, span_b = ichimoku(df)
    df["tenkan"] = tenkan
    df["kijun"] = kijun
    df["span_a"] = span_a
    df["span_b"] = span_b

    ema_fast = df["c"].ewm(span=12, adjust=False).mean()
    ema_slow = df["c"].ewm(span=26, adjust=False).mean()

    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    return df


def get_cloud_bounds(df):
    last = df.iloc[-1]
    cloud_top = max(last["span_a"], last["span_b"])
    cloud_bottom = min(last["span_a"], last["span_b"])
    return cloud_top, cloud_bottom


def has_bearish_tenkan_kijun_cross(df):
    recent = df.tail(3)

    if len(recent) < 2:
        return False

    for index in range(1, len(recent)):
        previous_tenkan = recent["tenkan"].iloc[index - 1]
        previous_kijun = recent["kijun"].iloc[index - 1]
        current_tenkan = recent["tenkan"].iloc[index]
        current_kijun = recent["kijun"].iloc[index]

        if (
            previous_tenkan >= previous_kijun
            and current_tenkan < current_kijun
        ):
            return True

    return False


def has_bearish_macd_cross(df):
    recent = df.tail(3)

    if len(recent) < 2:
        return False

    for index in range(1, len(recent)):
        previous_macd = recent["macd"].iloc[index - 1]
        previous_signal = recent["macd_signal"].iloc[index - 1]
        current_macd = recent["macd"].iloc[index]
        current_signal = recent["macd_signal"].iloc[index]

        if previous_macd >= previous_signal and current_macd < current_signal:
            return True

    return False


def is_bearish_chikou_free(df):
    if len(df) < 27:
        return False

    current_price = df["c"].iloc[-1]
    price_26_candles_ago_low = df["l"].iloc[-27]

    return current_price < price_26_candles_ago_low


def analyze_symbol(symbol):
    df_4h = prepare_indicators(get_data(symbol, "4h"))
    df_4h = df_4h.dropna().reset_index(drop=True)

    if len(df_4h) < 30:
        raise ValueError("Not enough OHLCV data.")

    last = df_4h.iloc[-1]
    cloud_top, cloud_bottom = get_cloud_bounds(df_4h)

    price_below_cloud = last["c"] < cloud_bottom
    tenkan_below_kijun = last["tenkan"] < last["kijun"]
    bearish_tk_cross = has_bearish_tenkan_kijun_cross(df_4h)
    bearish_macd_cross = has_bearish_macd_cross(df_4h)
    chikou_free = is_bearish_chikou_free(df_4h)

    score = 0
    score += 25 if price_below_cloud else 0
    score += 25 if bearish_tk_cross else 0
    score += 25 if bearish_macd_cross else 0
    score += 25 if chikou_free else 0

    rules_ok = (
        price_below_cloud
        and tenkan_below_kijun
        and bearish_tk_cross
        and bearish_macd_cross
        and chikou_free
    )

    signal = "SHORT" if rules_ok else "NONE"

    return {
        "symbol": symbol,
        "price": round(last["c"], 8),
        "signal": signal,
        "score": score,
        "price_below_cloud": price_below_cloud,
        "tenkan_below_kijun": tenkan_below_kijun,
        "bearish_tk_cross": bearish_tk_cross,
        "bearish_macd_cross": bearish_macd_cross,
        "chikou_free": chikou_free,
        "cloud_top": round(cloud_top, 8),
        "cloud_bottom": round(cloud_bottom, 8),
        "macd": round(last["macd"], 8),
        "macd_signal": round(last["macd_signal"], 8),
    }


def scan():
    results = []
    errors = []

    for sym in symbols:
        try:
            results.append(analyze_symbol(sym))
        except Exception as exc:
            errors.append(f"{sym}: {exc}")

    if not results:
        if errors:
            return (
                "⚠️ Unable to fetch market data for the scan.\n"
                f"Errors: {'; '.join(errors[:3])}"
            )
        return "❌ No setups found."

    results.sort(key=lambda item: item["score"], reverse=True)
    short_signals = [item for item in results if item["signal"] == "SHORT"]

    msg = "🎯 BEARISH ICHIMOKU + MACD SCANNER (4H)\n"
    msg += "═" * 70 + "\n\n"

    if short_signals:
        msg += "🔴 SHORT SIGNALS\n"
        msg += "─" * 70 + "\n\n"

        for item in short_signals:
            msg += (
                f"⭐ {item['symbol']}\n"
                f"  Price: {item['price']}\n"
                f"  Score: {item['score']}/100\n"
                f"  Below Cloud: {'YES' if item['price_below_cloud'] else 'NO'}\n"
                f"  Tenkan < Kijun: {'YES' if item['tenkan_below_kijun'] else 'NO'}\n"
                f"  Bearish TK Cross: {'YES' if item['bearish_tk_cross'] else 'NO'}\n"
                f"  Bearish MACD Cross: {'YES' if item['bearish_macd_cross'] else 'NO'}\n"
                f"  Chikou Free: {'YES' if item['chikou_free'] else 'NO'}\n"
            )
            msg += "─" * 70 + "\n"

        msg += "\n"
    else:
        msg += "🔔 NO SHORT SIGNALS MATCHING THE RULESET YET\n\n"

    msg += "📊 ALL COINS\n"
    msg += "─" * 70 + "\n\n"

    for item in results:
        icon = "🔴" if item["signal"] == "SHORT" else "⚪"

        msg += (
            f"{icon} {item['symbol']:<12} "
            f"Score: {item['score']:>3}/100  "
            f"Signal: {item['signal']:<5}  "
            f"Cloud: {'YES' if item['price_below_cloud'] else 'NO'}  "
            f"TK: {'YES' if item['bearish_tk_cross'] else 'NO'}  "
            f"MACD: {'YES' if item['bearish_macd_cross'] else 'NO'}  "
            f"Chikou: {'YES' if item['chikou_free'] else 'NO'}\n"
        )
        msg += "─" * 70 + "\n"

    if errors:
        msg += "\n⚠️ Symbols with fetch errors:\n"
        msg += "\n".join(errors[:5])

    return msg


if __name__ == "__main__":
    print(scan())