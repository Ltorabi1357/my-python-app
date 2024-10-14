import os
import requests
import schedule
import time
import logging
import hmac
import hashlib

# تنظیمات لاگ‌گیری
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# تنظیمات API CoinEx
API_KEY = 'B5896BCEEAC543DB8FE94264C1E91569'  # کلید API خود را وارد کنید
API_SECRET = 'E5F8FA9CCDDD2BF16604E5611F15F2479091840F83FC0AD7'  # کلید Secret خود را وارد کنید
BASE_URL = 'https://api.coinex.com/v1'

# URL وب‌هوک تریدینگ ویو
WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/20379273/21bjzz8/"  # اینجا URL وب‌هوک خود را قرار دهید

# تابع برای ایجاد امضای HMAC
def create_signature(api_secret, params):
    params_str = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    return hmac.new(api_secret.encode(), params_str.encode(), hashlib.sha256).hexdigest()

# تابع برای دریافت قیمت ارزهای دیجیتال از CoinMarketCap
def get_coinmarketcap_prices(crypto_symbols, api_key):
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    parameters = {
        'symbol': ','.join(crypto_symbols)  # ترکیب نمادها با کاما
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key.strip()  # حذف فاصله اضافی از کلید API
    }

    try:
        response = requests.get(url, params=parameters, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        return None

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Failed to retrieve data. Status code: {response.status_code}")
        return None

# تابع برای دریافت قیمت از CoinEx
def get_price(symbol):
    endpoint = '/market/ticker'
    params = {
        'market': symbol,
        'access_key': API_KEY,
        'tonce': int(time.time() * 1000)
    }
    params['sign'] = create_signature(API_SECRET, params)

    response = requests.get(BASE_URL + endpoint, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error: {response.status_code}, {response.text}")
        return None

# تابع برای خرید ارز
def place_order(symbol, side, amount, price):
    endpoint = '/order/place'
    params = {
        'market': symbol,
        'side': side,
        'amount': amount,
        'price': price,
        'access_key': API_KEY,
        'tonce': int(time.time() * 1000)
    }
    params['sign'] = create_signature(API_SECRET, params)

    response = requests.post(BASE_URL + endpoint, data=params)

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error: {response.status_code}, {response.text}")
        return None

# تابع به‌روزرسانی قیمت‌ها و انجام معاملات
def update_prices():
    crypto_symbols = ["BTC", "ETH", "XRP", "ADA", "DOGE", "DOT", "LTC", "BNB", "SOL", "LINK",
                      "AVAX", "UNI", "BCH", "ATOM", "XMR", "TON", "FTM", "SUI", "CAKE"]
    logger.info(f"Fetching prices for: {crypto_symbols}")
    prices = get_coinmarketcap_prices(crypto_symbols, api_key)

    if prices:
        logger.info("\nUpdated Prices:")
        for symbol in crypto_symbols:
            if symbol in prices.get('data', {}):
                try:
                    price = float(prices['data'][symbol]['quote']['USD']['price'])
                    logger.info(f"{symbol}: ${price:.2f}")

                    # دریافت قیمت از CoinEx
                    coinex_price_data = get_price(f'{symbol.upper()}USDT')
                    if coinex_price_data:
                        coinex_price = float(coinex_price_data['data']['ticker']['last'])
                        logger.info(f"CoinEx Price for {symbol}: {coinex_price}")

                        # بررسی تغییر قیمت 0.5%
                        price_change = ((price - coinex_price) / coinex_price) * 100

                        if abs(price_change) >= 0.5:  # تغییر قیمت 0.5%
                            logger.info(f"Price change alert for {symbol}: {price_change:.2f}%")
                            notify_tradingview(symbol, price, price_change)

                except ValueError:
                    logger.warning(f"Price for {symbol} is not a valid number.")

            else:
                logger.warning(f"No data found for symbol {symbol}.")
    else:
        logger.error("Failed to update prices.")

# تابع برای ارسال اطلاعیه به تریدینگ ویو
def notify_tradingview(symbol, price, change):
    payload = {
        "symbol": symbol,
        "price": price,
        "change": change
    }
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logger.info(f"Notification sent to TradingView for {symbol}: {payload}")
        else:
            logger.error(f"Failed to send notification: {response.status_code}, {response.text}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

# کلید API را از متغیرهای محیطی دریافت کنید
os.environ["CMC_API_KEY"] = "d436d4c2-a371-4464-8280-b318ff257b05"  # کلید API CoinMarketCap
api_key = os.getenv("CMC_API_KEY")

if not api_key:
    raise ValueError("Please set the CMC_API_KEY environment variable.")

# تنظیم برنامه‌ریزی برای به‌روزرسانی قیمت‌ها هر 15 دقیقه
schedule.every(1).minutes.do(update_prices)

# پیام آغاز به کار
logger.info("Price updater is running...")

# اجرای دائمی برنامه
while True:
    try:
        schedule.run_pending()  # بررسی زمان‌بندی‌ها
        time.sleep(60)  # تأخیر 60 ثانیه برای بهینه‌سازی منابع
    except KeyboardInterrupt:
        logger.info("Program stopped manually.")
        break
    except Exception as e:
        logger.error(f"An error occurred in the main loop: {e}")
        time.sleep(5)  # در صورت خطا، یک تأخیر ایجاد می‌کند و دوباره تلاش می‌کند
