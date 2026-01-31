import requests
from fastapi import HTTPException

from utils import get_base_url, authenticator


def query_transaction_status(tenant, transaction_id: str, result_url: str, timeout_url: str):
    """
    Query M-Pesa transaction status. Uses tenant's initiator, security_credential, shortcode;
    result_url and timeout_url are shared (from config).
    """
    base_url = get_base_url(tenant.environment)
    url = f"{base_url}mpesa/transactionstatus/v1/query"
    token = authenticator(tenant.consumer_key, tenant.consumer_secret, base_url)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "Initiator": tenant.initiator_name,
        "SecurityCredential": tenant.security_credential,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id,
        "PartyA": tenant.business_short_code,
        "IdentifierType": "4",
        "ResultURL": result_url,
        "QueueTimeOutURL": timeout_url,
        "Remarks": "Transaction status query",
        "Occasion": "Query",
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()
    raise HTTPException(
        status_code=response.status_code,
        detail=f"Transaction status query failed: {response.text}",
    )
