import os, sys


IS_COMPILED = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

if IS_COMPILED:
    # noinspection PyProtectedMember
    BUNDLE_DIR = getattr(sys, '_MEIPASS')
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_COMPILED:
    # C:\Users\<User>\AppData\Roaming\VennLedger or Home folder
    app_data_base = os.getenv('APPDATA', os.path.expanduser('~'))
    USER_DATA_DIR = os.path.join(app_data_base, "VennLedger")
else:
    USER_DATA_DIR = BUNDLE_DIR

ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets")

DB_DIR = os.path.join(USER_DATA_DIR, "database")
USER_CONFIG_DIR = os.path.join(USER_DATA_DIR, "config")
LOG_DIR = os.path.join(USER_DATA_DIR, "logs")
DB_PATH = os.path.join(DB_DIR, "tracker.db")
CREDENTIALS_PATH = os.path.join(USER_CONFIG_DIR, "credentials.json")
TOKEN_PATH = os.path.join(USER_CONFIG_DIR, "token.json")
CONFIG_PATH = os.path.join(USER_CONFIG_DIR, "ui_prefs.json")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(USER_CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

CURRENCY_SYMBOLS = {
    "EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "INR": "₹", "KRW": "₩", "RUB": "₽", "ILS": "₪", "THB": "฿",
    "VND": "₫", "PHP": "₱", "NGN": "₦", "ZAR": "R",

    "CAD": "$", "AUD": "$", "NZD": "$", "MXN": "$", "ARS": "$",
    "CLP": "$", "COP": "$", "SGD": "$", "HKD": "$",

    "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "ISK": "kr",
    "BRL": "R$", "PLN": "zł", "CZK": "Kč", "HUF": "Ft", "RON": "lei",
    "IDR": "Rp", "MYR": "RM", "AED": "د.إ", "SAR": "﷼"
}


