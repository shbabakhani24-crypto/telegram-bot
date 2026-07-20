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
    "BLUR/USDT"
]


def get_data(symbol, tf="4h"):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=200)
    df = pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])
    return df


def prepare_ichimoku(df):
    df = df.copy()
    tenkan, kijun, span_a, span_b = ichimoku(df)
    df["tenkan"] = tenkan
    df["kijun"] = kijun
    df["span_a"] = span_a
    df["span_b"] = span_b
    return df


def get_cloud_bounds(df):
    last = df.iloc[-1]
    cloud_top = max(last["span_a"], last["span_b"])
    cloud_bottom = min(last["span_a"], last["span_b"])
    return cloud_top, cloud_bottom


def get_h4_cross_strength(df_4h, direction):
    recent = df_4h.tail(3).copy()
    if recent.empty:
        return 0

    if direction == "LONG":
        for i in range(1, len(recent)):
            if recent["tenkan"].iloc[i] > recent["kijun"].iloc[i] and recent["tenkan"].iloc[i - 1] <= recent["kijun"].iloc[i - 1]:
                return 30
        if recent["tenkan"].iloc[-1] > recent["kijun"].iloc[-1]:
            return 15
        return 0

    if direction == "SHORT":
        for i in range(1, len(recent)):
            if recent["tenkan"].iloc[i] < recent["kijun"].iloc[i] and recent["tenkan"].iloc[i - 1] >= recent["kijun"].iloc[i - 1]:
                return 30
        if recent["tenkan"].iloc[-1] < recent["kijun"].iloc[-1]:
            return 15
        return 0

    return 0


def get_future_cloud_score(df_4h, direction):
    last = df_4h.iloc[-1]
    if direction == "LONG":
        return 20 if last["span_a"] > last["span_b"] else 0
    if direction == "SHORT":
        return 20 if last["span_a"] < last["span_b"] else 0
    return 0


def get_chikou_score(df_4h, direction):
    price = df_4h["c"].iloc[-1]
    chikou_series = df_4h["c"].shift(26)
    chikou_value = chikou_series.dropna().iloc[-1] if chikou_series.notna().any() else price

    if direction == "LONG":
        return 20 if chikou_value > price else -20
    if direction == "SHORT":
        return 20 if chikou_value < price else -20
    return 0


def analyze_symbol(symbol):
    df_4h = prepare_ichimoku(get_data(symbol, "4h"))
    df_1d = prepare_ichimoku(get_data(symbol, "1d"))

    last_d = df_1d.iloc[-1]
    daily_cloud_top, daily_cloud_bottom = get_cloud_bounds(df_1d)

    if last_d["c"] > daily_cloud_top:
        direction = "LONG"
        trend_alignment = 30
    elif last_d["c"] < daily_cloud_bottom:
        direction = "SHORT"
        trend_alignment = 30
    else:
        direction = "NONE"
        trend_alignment = 0

    score = trend_alignment
    cross_strength = get_h4_cross_strength(df_4h, direction)
    future_cloud_score = get_future_cloud_score(df_4h, direction)
    chikou_score = get_chikou_score(df_4h, direction)

    score += cross_strength + future_cloud_score + chikou_score

    if direction == "LONG":
        rules_ok = (
            last_d["c"] > daily_cloud_top and
            cross_strength >= 15 and
            future_cloud_score == 20 and
            chikou_score == 20
        )
    elif direction == "SHORT":
        rules_ok = (
            last_d["c"] < daily_cloud_bottom and
            cross_strength >= 15 and
            future_cloud_score == 20 and
            chikou_score == 20
        )
    else:
        rules_ok = False

    if score >= 80 and rules_ok:
        signal = "LONG" if direction == "LONG" else "SHORT"
    else:
        signal = "NONE"

    return {
        "symbol": symbol,
        "price": round(df_4h["c"].iloc[-1], 8),
        "mode": direction,
        "signal": signal,
        "score": round(score, 2),
        "trend_alignment": trend_alignment,
        "cross_strength": cross_strength,
        "future_cloud_score": future_cloud_score,
        "chikou_score": chikou_score,
        "daily_cloud_top": round(daily_cloud_top, 8),
        "daily_cloud_bottom": round(daily_cloud_bottom, 8),
    }


def scan():
    results = []
    errors = []

    for sym in symbols:
        try:
            result = analyze_symbol(sym)
            results.append(result)
        except Exception as exc:
            errors.append(f"{sym}: {exc}")
            continue

    if not results:
        if errors:
            return (
                "⚠️ Unable to fetch market data for the scan.\n"
                f"Errors: {'; '.join(errors[:3])}"
            )
        return "❌ No setups found."

    results.sort(key=lambda x: x["score"], reverse=True)

    long_signals = [r for r in results if r["signal"] == "LONG"]
    short_signals = [r for r in results if r["signal"] == "SHORT"]

    msg = "🎯 BIASED ICHIMOKU SCANNER\n"
    msg += "═" * 70 + "\n\n"

    if long_signals:
        msg += "🟢 LONG SIGNALS ✅\n"
        msg += "─" * 70 + "\n\n"
        for item in long_signals:
            msg += (
                f"⭐ {item['symbol']}\n"
                f"  Score: {item['score']:.0f} | Mode: {item['mode']}\n"
                f"  Trend: +30 | Cross: {item['cross_strength']} | Future Cloud: {item['future_cloud_score']} | Chikou: {item['chikou_score']}\n"
            )
            msg += "─" * 70 + "\n"
        msg += "\n"

    if short_signals:
        msg += "🔴 SHORT SIGNALS ❌\n"
        msg += "─" * 70 + "\n\n"
        for item in short_signals:
            msg += (
                f"⭐ {item['symbol']}\n"
                f"  Score: {item['score']:.0f} | Mode: {item['mode']}\n"
                f"  Trend: +30 | Cross: {item['cross_strength']} | Future Cloud: {item['future_cloud_score']} | Chikou: {item['chikou_score']}\n"
            )
            msg += "─" * 70 + "\n"
        msg += "\n"

    if not long_signals and not short_signals:
        msg += "🔔 NO SIGNALS MATCHING THE BIASED ICHIMOKU RULESET YET\n\n"

    msg += "📊 ALL COINS\n"
    msg += "─" * 70 + "\n\n"

    for item in results:
        icon = "🟢" if item["signal"] == "LONG" else "🔴" if item["signal"] == "SHORT" else "⚪"
        msg += (
            f"{icon} {item['symbol']:<12}  "
            f"Score: {item['score']:>5.0f}  "
            f"Signal: {item['signal']:<5}  "
            f"Mode: {item['mode']:<5}\n"
        )
        msg += "─" * 70 + "\n"

    return msg


if __name__ == "__main__":
    print(scan())