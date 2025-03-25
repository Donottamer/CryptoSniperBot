
import time
import requests
import pandas as pd
import ta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import numpy as np
from scipy.signal import argrelextrema

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

# === Google Sheets Logging ===
def log_to_sheet(symbol, signal, entry, target, stop_loss, confidence):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('google_creds.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("CryptoSignals").worksheet("Signals")
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, signal, entry, target, stop_loss, confidence]
    sheet.append_row(row)

# === Binance Candle Fetcher ===
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

# === Swing Highs and Lows Detection ===
def get_support_resistance(df, order=3):
    lows = df['low'].values
    highs = df['high'].values
    local_mins = argrelextrema(lows, np.less_equal, order=order)[0]
    local_maxs = argrelextrema(highs, np.greater_equal, order=order)[0]
    support = df['low'].iloc[local_mins[-1]] if len(local_mins) > 0 else df['low'].min()
    resistance = df['high'].iloc[local_maxs[-1]] if len(local_maxs) > 0 else df['high'].max()
    return support, resistance

# === Signal Logic with Multi-Timeframe + Advanced S/R ===
def analyze(symbol):
    df_1m = fetch_data(symbol, interval="1m", limit=100)
    df_5m = fetch_data(symbol, interval="5m", limit=50)

    # Indicators on 1m
    df_1m['ema_fast'] = ta.trend.EMAIndicator(close=df_1m['close'], window=5).ema_indicator()
    df_1m['ema_slow'] = ta.trend.EMAIndicator(close=df_1m['close'], window=20).ema_indicator()
    df_1m['rsi'] = ta.momentum.RSIIndicator(close=df_1m['close'], window=14).rsi()
    df_1m['macd_hist'] = ta.trend.MACD(close=df_1m['close']).macd_diff()
    df_1m['atr'] = ta.volatility.AverageTrueRange(high=df_1m['high'], low=df_1m['low'], close=df_1m['close']).average_true_range()

    # Indicators on 5m
    ema_5m_fast = ta.trend.EMAIndicator(close=df_5m['close'], window=5).ema_indicator()
    ema_5m_slow = ta.trend.EMAIndicator(close=df_5m['close'], window=20).ema_indicator()
    df_5m['ema_fast'] = ema_5m_fast
    df_5m['ema_slow'] = ema_5m_slow

    # Latest values
    latest = df_1m.iloc[-1]
    price = round(latest['close'], 4)
    ef, es, r, macd, v, atr_val = latest[['ema_fast', 'ema_slow', 'rsi', 'macd_hist', 'volume', 'atr']]

    body_size = abs(latest['close'] - latest['open'])
    avg_body = df_1m['close'].sub(df_1m['open']).abs().rolling(10).mean().iloc[-1]
    big_candle = body_size > avg_body * 1.2

    avg_volume = df_1m['volume'].rolling(20).mean().iloc[-1]
    volume_spike = v > avg_volume * 1.3

    momentum_ok = macd > 0 if ef > es else macd < 0
    rsi_ok = (r > 50 if ef > es else r < 50)

    # === Multi-Timeframe Confirmation ===
    tf5_latest = df_5m.iloc[-1]
    tf5_fast = tf5_latest['ema_fast']
    tf5_slow = tf5_latest['ema_slow']
    tf5_agree = (ef > es and tf5_fast > tf5_slow) or (ef < es and tf5_fast < tf5_slow)

    # === Improved Support/Resistance ===
    support, resistance = get_support_resistance(df_1m)
    near_support = abs(price - support) / price < 0.005
    near_resistance = abs(price - resistance) / price < 0.005

    volatility_ok = atr_val > 0.0015 * price

    if ef > es and near_support and tf5_agree:
        signal = "LONG"
        target = round(price * 1.03, 4)
        stop_loss = round(support * 0.997, 4)
    elif ef < es and near_resistance and tf5_agree:
        signal = "SHORT"
        target = round(price * 0.97, 4)
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
    score += 15 if tf5_agree else 0
    confidence = min(100, score)

    return signal, price, target, stop_loss, round(confidence, 2)

# === Main Bot Loop ===
symbols = {
    "XRP": "XRPUSDT",
    "SOL": "SOLUSDT",
    "ADA": "ADAUSDT"
}

while True:
    for name, symbol in symbols.items():
        try:
            signal, entry, target, stop_loss, confidence = analyze(symbol)

            if signal in ["LONG", "SHORT"] and confidence >= 70:
                msg = (
                    f"📈 {name} Signal: {signal}\n"
                    f"Entry: ${entry}\n"
                    f"Target (3%): ${target}\n"
                    f"Stop-Loss: ${stop_loss}\n"
                    f"Confidence: {confidence}%"
                )
                print(msg)
                send_telegram(msg)
                log_to_sheet(name, signal, entry, target, stop_loss, confidence)
            else:
                print(f"{name}: HOLD or Low Signal @ ${entry} | Confidence: {confidence}%")

        except Exception as e:
            print(f"Error with {name}: {e}")

    time.sleep(60)
