import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "Temp")
DB_PATH = os.path.join(BASE_DIR, "data.sqlite3")

DEFAULT_QUOTA_BYTES = 4 * 1024 * 1024 * 1024  # 4GB
DEFAULT_CLEANUP_INTERVAL_SECONDS = 60

MAX_CONTENT_LENGTH = 4 * 1024 * 1024 * 1024  # 2GB（你也可以調小）