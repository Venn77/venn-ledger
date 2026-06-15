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
    "EUR": {"symbol": "€", "decimals": 2, "name": "Eurozone Euro"},
    "USD": {"symbol": "$", "decimals": 2, "name": "US Dollar"},
    "GBP": {"symbol": "£", "decimals": 2, "name": "British Pound"},
    "JPY": {"symbol": "¥", "decimals": 0, "name": "Japanese Yen"},
    "CNY": {"symbol": "¥", "decimals": 2, "name": "Chinese Yuan"},
    "INR": {"symbol": "₹", "decimals": 2, "name": "Indian Rupee"},
    "KRW": {"symbol": "₩", "decimals": 0, "name": "South Korean Won"},
    "RUB": {"symbol": "₽", "decimals": 2, "name": "Russian Ruble"},
    "ILS": {"symbol": "₪", "decimals": 2, "name": "Israeli Shekel"},
    "THB": {"symbol": "฿", "decimals": 2, "name": "Thai Baht"},
    "VND": {"symbol": "₫", "decimals": 0, "name": "Vietnamese Dong"},
    "PHP": {"symbol": "₱", "decimals": 2, "name": "Philippine Peso"},
    "NGN": {"symbol": "₦", "decimals": 2, "name": "Nigerian Naira"},
    "ZAR": {"symbol": "R", "decimals": 2, "name": "South African Rand"},

    "CAD": {"symbol": "$", "decimals": 2, "name": "Canadian Dollar"},
    "AUD": {"symbol": "$", "decimals": 2, "name": "Australian Dollar"},
    "NZD": {"symbol": "$", "decimals": 2, "name": "New Zealand Dollar"},
    "MXN": {"symbol": "$", "decimals": 2, "name": "Mexican Peso"},
    "ARS": {"symbol": "$", "decimals": 2, "name": "Argentine Peso"},
    "CLP": {"symbol": "$", "decimals": 0, "name": "Chilean Peso"},
    "COP": {"symbol": "$", "decimals": 0, "name": "Colombian Peso"},
    "SGD": {"symbol": "$", "decimals": 2, "name": "Singapore Dollar"},
    "HKD": {"symbol": "$", "decimals": 2, "name": "Hong Kong Dollar"},

    "CHF": {"symbol": "CHF", "decimals": 2, "name": "Swiss Franc"},
    "SEK": {"symbol": "kr", "decimals": 2, "name": "Swedish Krona"},
    "NOK": {"symbol": "kr", "decimals": 2, "name": "Norwegian Krone"},
    "DKK": {"symbol": "kr", "decimals": 2, "name": "Danish Krone"},
    "ISK": {"symbol": "kr", "decimals": 0, "name": "Icelandic Króna"},
    "BRL": {"symbol": "R$", "decimals": 2, "name": "Brazilian Real"},
    "PLN": {"symbol": "zł", "decimals": 2, "name": "Polish Zloty"},
    "CZK": {"symbol": "Kč", "decimals": 2, "name": "Czech Koruna"},
    "HUF": {"symbol": "Ft", "decimals": 0, "name": "Hungarian Forint"},
    "RON": {"symbol": "lei", "decimals": 2, "name": "Romanian Leu"},
    "IDR": {"symbol": "Rp", "decimals": 0, "name": "Indonesian Rupiah"},
    "MYR": {"symbol": "RM", "decimals": 2, "name": "Malaysian Ringgit"},
    "AED": {"symbol": "د.إ", "decimals": 2, "name": "UAE Dirham"},
    "SAR": {"symbol": "﷼", "decimals": 2, "name": "Saudi Riyal"}
}


