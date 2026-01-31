import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64


def get_base_url(environment: str) -> str:
    if (environment or "").lower() == "sandbox":
        return "https://sandbox.safaricom.co.ke/"
    return "https://api.safaricom.co.ke/"


def authenticator(consumer_key: str, consumer_secret: str, base_url: str) -> str:
    print("Am Hereeee")
    print("cons_key", consumer_key)
    print("cons_sec", consumer_secret)
    base_url="https://api.safaricom.co.ke/"
    url = f"{base_url}oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    i=r.json()
    print("JJJ", i)
    if r.status_code != 200:
        raise ValueError(
            f"M-Pesa OAuth failed (status {r.status_code}). "
            f"Check consumer_key, consumer_secret, and environment. Response: {r.text[:300]}"
        )
    try:
        data = r.json()
    except Exception as e:
        raise ValueError(
            f"M-Pesa OAuth returned invalid JSON. Response: {r.text[:200]}"
        ) from e
    if "access_token" not in data:
        raise ValueError(
            f"M-Pesa OAuth response missing access_token. Response: {data}"
        )
    return data["access_token"]


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_password(business_short_code: str, passkey: str) -> str:
    password_to_encrypt = business_short_code + passkey + get_timestamp()
    return base64.b64encode(password_to_encrypt.encode()).decode("utf-8")
