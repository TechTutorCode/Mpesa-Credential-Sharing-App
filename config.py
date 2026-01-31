import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stk_push.db")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://m-pesa.example.com").rstrip("/")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Shared callback paths (same for all tenants)
CALLBACK_URL_STK = f"{APP_BASE_URL}/callbackurl"
CALLBACK_URL_VALIDATION = f"{APP_BASE_URL}/validationurl"
CALLBACK_URL_CONFIRMATION = f"{APP_BASE_URL}/confirmationurl"
CALLBACK_URL_RESULT = f"{APP_BASE_URL}/resulturl"
CALLBACK_URL_TIMEOUT = f"{APP_BASE_URL}/timeouturl"
