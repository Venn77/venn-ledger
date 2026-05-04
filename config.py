import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DB_DIR = os.path.join(PROJECT_ROOT, "database")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

DB_PATH = os.path.join(DB_DIR, "tracker.db")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials.json")
TOKEN_PATH = os.path.join(CONFIG_DIR, "token.json")

if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)


