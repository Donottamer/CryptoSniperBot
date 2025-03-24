
import time
import requests
import pandas as pd
import ta

# === Telegram Setup ===
TELEGRAM_TOKEN = "7908508903:AAF8jHtvcwy3CFNbRLr3dFqrP8tIfFwdons"
TELEGRAM_CHAT_ID = "7880744999"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

# === Symbols to Watch ===
symbols = {
    "XRP": "XRPUSDT",
    "SOL": "SOLUSDT",
    "ADA": "ADAUSDT",
    "ETH": "ETHUSDT",
    "FARTCOIN": "FARTCOINUSDT",
    "PI": "PIUSDT",
    "ALGO": "ALGOUSDT",
    "IOTA": "IOTAUSDT"
}

# === Fetch Binance Candle Data ===
def fetch_data(symbol, interval="1m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'num_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    df['volume'] = pd.to_numeric(df['volume'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    df['open'] = pd.to_numeric(df['open'])
    return df

# === Analyze with Indicators and Generate Signal ===
def analyze(df):
    ema_fast = ta.trend.EMAIndicator(close=df['close'], window=5).ema_indicator()
    ema_slow = ta.trend.EMAIndicator(close=df['close'], window=20).ema_indicator()
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd_hist = ta.trend.MACD(close=df['close']).macd_diff()
    atr = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close']).average_true_range()

    df['ema_fast'] = ema_fast
    df['ema_slow'] = ema_slow
    df['rsi'] = rsi
    df['macd_hist'] = macd_hist
    df['atr'] = atr

    latest = df.iloc[-1]
    price = round(latest['close'], 4)
    ef, es, r, macd, v, atr_val = latest[['ema_fast', 'ema_slow', 'rsi', 'macd_hist', 'volume', 'atr']]

    body_size = abs(latest['close'] - latest['open'])
    avg_body = df['close'].sub(df['open']).abs().rolling(10).mean().iloc[-1]
    big_candle = body_size > avg_body * 1.2

    avg_volume = df['volume'].rolling(20).mean().iloc[-1]
    volume_spike = v > avg_volume * 1.3

    momentum_ok = macd > 0 if ef > es else macd < 0
    rsi_ok = (r > 50 if ef > es else r < 50)

    support = df['low'].rolling(20).min().iloc[-1]
    resistance = df['high'].rolling(20).max().iloc[-1]
    near_support = abs(price - support) / price < 0.005
    near_resistance = abs(price - resistance) / price < 0.005

    volatility_ok = atr_val > 0.0015 * price

    if ef > es and near_support:
        signal = "LONG"
        target = round(price * 1.01, 4)
        stop_loss = round(support * 0.997, 4)
    elif ef < es and near_resistance:
        signal = "SHORT"
        target = round(price * 0.99, 4)
        stop_loss = round(resistance * 1.003, 4)
    else:
        signal = "HOLD"
        target = None
        stop_loss = None

    score = 0
    score += 20 if volume_spike else 0
    score += 20 if momentum_ok else 0
    score += 15 if rsi_ok else 0
    score += 15 if big_candle else 0
    score += 15 if volatility_ok else 0
    score += 15 if (near_support if signal == "LONG" else near_resistance if signal == "SHORT" else False) else 0
    confidence = min(100, score)

    return signal, price, target, stop_loss, round(confidence, 2)

# === Bot Loop (checks every 60 seconds) ===
while True:
    for name, symbol in symbols.items():
        try:
            df = fetch_data(symbol)
            signal, entry, target, stop_loss, confidence = analyze(df)

            if signal in ["LONG", "SHORT"] and confidence >= 65:
                msg = (
                    f"📈 {name} Signal: {signal}\n"
                    f"Entry: ${entry}\n"
                    f"Target: ${target}\n"
                    f"Stop-Loss: ${stop_loss}\n"
                    f"Confidence: {confidence}%"
                )
                print(msg)
                send_telegram(msg)
            else:
                print(f"{name}: HOLD or Low Signal @ ${entry} | Confidence: {confidence}%")

        except Exception as e:
            print(f"Error with {name}: {e}")
    
    time.sleep(60)
