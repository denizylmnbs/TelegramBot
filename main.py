import ccxt
import pandas as pd
import ta
import requests
import time
from dotenv import load_dotenv
import os
from binance.client import Client

# Load API from .env file
load_dotenv("config\.env")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Ensure logs directory exists
os.makedirs("data", exist_ok=True)

def log_signal(symbol, action, price, stop_loss, take_profit):
    log_entry = {
        "timestamp": pd.Timestamp.now(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit
    }
    log_file = "data/logs.csv"
    if not os.path.exists(log_file):
        pd.DataFrame([log_entry]).to_csv(log_file, index=False)
    else:
        pd.DataFrame([log_entry]).to_csv(log_file, mode='a', header=False, index=False)

# Send a message from bot
def send_telegram_message(bot_token, chat_id, symbol, action, price, stop_loss, take_profit):
    message = (
        f"Trade Signal: {action}\nSymbol: {symbol}\nCurrent Price: {price:.2f}\nStop Loss: {stop_loss:.2f}\nTake Profit: {take_profit:.2f}"
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {'chat_id': chat_id, 'text': message}
    response = requests.post(url, params=params)
    return response.json()

# Calculate RSI indicator
def calculate_rsi(dataframe, period=14):
    dataframe["RSI"] = ta.momentum.RSIIndicator(dataframe['close'], window=period).rsi()
    return dataframe

# Fetch price information and analyse with RSI
def fetch_and_analyze(api_key, api_secret, symbol, interval, bot_token, chat_id):
    client = Client(api_key, api_secret)
    klines = client.get_historical_klines(symbol, interval, "1 day ago UTC")

    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])
    df['close'] = df['close'].astype(float)

    df = calculate_rsi(df)

    short_sma = df['close'].rolling(window=7).mean().iloc[-1]
    long_sma = df['close'].rolling(window=25).mean().iloc[-1]
    rsi = df['RSI'].iloc[-1]

    current_price = df['close'].iloc[-1]
    support = df['close'].min()
    resistance = df['close'].max()

    action, stop_loss, take_profit = combined_strategy(current_price, short_sma, long_sma, rsi, support, resistance)

    if action != "Hold":
        send_telegram_message(bot_token, chat_id, symbol, action, current_price, stop_loss, take_profit)
        log_signal(symbol, action, current_price, stop_loss, take_profit)

# Trade strategy
def combined_strategy(price, short_sma, long_sma, rsi, support, resistance):
    if rsi <= 30 and short_sma > long_sma and price <= support:
        action = "Strong Buy"
    elif rsi >= 70 and long_sma > short_sma and price >= resistance:
        action = "Strong Sell"
    elif rsi >= 70:
        action = "Sell"
    elif rsi <= 30:
        action = "Buy"
    elif short_sma > long_sma:
        action = "Buy"
    elif long_sma > short_sma:
        action = "Sell"
    else:
        action = "Hold"

    stop_loss = 0.98 * support
    take_profit = 0.98 * resistance

    return action, stop_loss, take_profit

if __name__ == "__main__":
    client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
    while True:
        symbols = [symbol['symbol'] for symbol in client.get_exchange_info()['symbols'] if symbol['symbol'].endswith('USDT')]
        for symbol in symbols:
            try:
                print(f"{symbol} analiz ediliyor...")
                fetch_and_analyze(BINANCE_API_KEY, BINANCE_SECRET_KEY, symbol, "1h", TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            except Exception as e:
                print(f"{symbol} analiz edilirken hata oluştu: {e}")
        print("Tüm paritelerin analizi tamamlandı, bir sonraki kontrol için 1 saat bekleniyor...")
        time.sleep(3600)


# Strateji çok düz bu yüzden hatalı sinyaller üretiliyor. 
# Bazı coinler için aynı al-sat fiyat seviyelerini önerebiliyor özellikle çok sıfırlı coinlerde
# Sell sinyali için take profit ve destek noktaları long sinyaline göre yapılmış

# Yeni strateji geliştir ve take-profit ile stop-loss noktalarını daha uygun hale getir.