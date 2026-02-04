import logging
import sys
import requests
import pytz
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

from fastapi import FastAPI, HTTPException, Request, Depends, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import (
    DATABASE_URL,
    CALLBACK_URL_STK,
    CALLBACK_URL_VALIDATION,
    CALLBACK_URL_CONFIRMATION,
    CALLBACK_URL_RESULT,
    CALLBACK_URL_TIMEOUT,
)
from database import Base, App, Credential, StkPushTransaction, Transaction, generate_api_key, generate_credential_id, generate_account_number
from schema import (
    RegisterAppRequest,
    RegisterAppResponse,
    UpdateAppRequest,
    RegisterPaybillRequest,
    RegisterPaybillResponse,
    UpdatePaybillRequest,
    STKPushPayload,
    RegisterUrlPayload,
)
from utils import get_base_url, authenticator, get_timestamp, generate_password
from query import query_transaction_status

# Engine and session
if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_app_from_header(
    request: Request,
    x_api_key: Optional[str] = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> App:
    """Resolve app from X-API-Key header. Required for all routes except POST /apps and callbacks."""
    api_key = x_api_key or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    app = db.query(App).filter(App.api_key == api_key).first()
    if not app:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return app


def get_credential_for_app(app: App, credential_id: str, db: Session) -> Credential:
    """Get credential by credential_id and verify it belongs to the app."""
    cred = db.query(Credential).filter(Credential.credential_id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    if cred.app_id != app.id:
        raise HTTPException(status_code=403, detail="Credential does not belong to this app")
    if not cred.is_active:
        raise HTTPException(status_code=403, detail="Credential is inactive")
    return cred


app = FastAPI(
    title="M-Pesa Credential Sharing API",
    description="Register apps, add paybills, and use M-Pesa APIs. **Authenticate:** Click **Authorize** (lock icon) and enter your `api_key`.",
    swagger_ui_parameters={"persistAuthorization": True},
)


@app.exception_handler(ValueError)
def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# --- App registration ---

@app.post("/apps", response_model=RegisterAppResponse)
def register_app(payload: RegisterAppRequest, db: Session = Depends(get_db)):
    """Register a new app. Returns name, account_number (3-letter, unique), api_key, callback_url, created_at, updated_at."""
    api_key = generate_api_key()
    account_number = generate_account_number(db)
    row = App(name=payload.name, account_number=account_number, api_key=api_key, callback_url=payload.callback_url)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.patch("/apps", response_model=RegisterAppResponse)
def update_app(
    payload: UpdateAppRequest,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    """Update the authenticated app. Only provided fields are updated."""
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)
    return app


# --- Paybill registration ---

@app.post("/paybills", response_model=RegisterPaybillResponse)
def register_paybill(
    payload: RegisterPaybillRequest,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    """Register a new paybill under the app. Same schema as /admin/credentials except api_key. Returns credential_id."""
    credential_id = generate_credential_id()
    row = Credential(
        app_id=app.id,
        credential_id=credential_id,
        name=payload.name,
        consumer_key=payload.consumer_key,
        consumer_secret=payload.consumer_secret,
        business_short_code=payload.business_short_code,
        passkey=payload.passkey,
        initiator_name=payload.initiator_name,
        security_credential=payload.security_credential,
        environment=payload.environment or "production",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RegisterPaybillResponse(
        credential_id=row.credential_id,
        name=row.name,
        business_short_code=row.business_short_code,
        environment=row.environment,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@app.get("/paybills", response_model=List[RegisterPaybillResponse])
def list_paybills(
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    """List all paybills for the app."""
    rows = db.query(Credential).filter(Credential.app_id == app.id).all()
    return [
        RegisterPaybillResponse(
            credential_id=r.credential_id,
            name=r.name,
            business_short_code=r.business_short_code,
            environment=r.environment,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@app.patch("/paybills/{credential_id}", response_model=RegisterPaybillResponse)
def update_paybill(
    credential_id: str,
    payload: UpdatePaybillRequest,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    """Update an existing paybill. Only provided fields are updated."""
    cred = get_credential_for_app(app, credential_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cred, key, value)
    db.commit()
    db.refresh(cred)
    return RegisterPaybillResponse(
        credential_id=cred.credential_id,
        name=cred.name,
        business_short_code=cred.business_short_code,
        environment=cred.environment,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


# --- STK Push ---

@app.post("/stkpush")
def stk_push(
    payload: STKPushPayload,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    phone_number = payload.phoneNumber
    account_number = payload.accountNumber
    amount = payload.amount

    # Step 1: Resolve credential
    try:
        cred = get_credential_for_app(app, payload.credential_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("STK Push step 1 failed: credential lookup")
        raise HTTPException(status_code=500, detail=f"Credential lookup failed: {str(e)}")

    base_url = get_base_url(cred.environment)
    logger.info(
        "STK Push request: credential_id=%s, phone=%s, amount=%s, shortcode=%s, env=%s",
        (payload.credential_id[:8] + "...") if len(payload.credential_id) > 8 else payload.credential_id,
        phone_number,
        amount,
        cred.business_short_code,
        cred.environment,
    )

    # Step 2: Get OAuth token
    try:
        token = authenticator(cred.consumer_key, cred.consumer_secret, base_url)
    except ValueError as e:
        logger.error("STK Push step 2 failed: OAuth token. %s", str(e))
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")
    except Exception as e:
        logger.exception("STK Push step 2 failed: OAuth token")
        raise HTTPException(status_code=500, detail=f"OAuth failed: {str(e)}")

    # Step 3: Call Safaricom STK Push API
    url = f"{base_url}mpesa/stkpush/v1/processrequest"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    body = {
        "BusinessShortCode": cred.business_short_code,
        "Password": generate_password(cred.business_short_code, cred.passkey),
        "Timestamp": get_timestamp(),
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": cred.business_short_code,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL_STK,
        "AccountReference": account_number,
        "TransactionDesc": (payload.transactionDescription or "Payment")[:13],
    }

    try:
        response = requests.post(url, json=body, headers=headers)
    except requests.exceptions.RequestException as e:
        logger.exception("STK Push step 3 failed: network error calling Safaricom API")
        raise HTTPException(
            status_code=502,
            detail=f"Network error calling Safaricom: {str(e)}",
        )

    # Log raw Safaricom response
    logger.info(
        "Safaricom STK Push response: status=%s, body=%s",
        response.status_code,
        response.text[:500] if response.text else "(empty)",
    )

    # Parse JSON response
    try:
        r = response.json()
    except Exception as e:
        logger.error(
            "STK Push step 3 failed: Safaricom returned invalid JSON. status=%s, body=%s",
            response.status_code,
            response.text[:300],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Safaricom returned invalid JSON (status {response.status_code}). Response: {response.text[:200]}",
        )

    # Check for Safaricom error response
    if "errorCode" in r or "requestId" in r:
        error_code = r.get("errorCode", "unknown")
        error_msg = r.get("errorMessage", r.get("error", str(r)))
        logger.error(
            "STK Push step 3 failed: Safaricom error. code=%s, message=%s, full=%s",
            error_code,
            error_msg,
            r,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Safaricom error (code {error_code}): {error_msg}",
        )

    # Check for success (MerchantRequestID present)
    if "MerchantRequestID" not in r:
        logger.error(
            "STK Push step 3 failed: unexpected response structure. full=%s",
            r,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid STK Push response: Missing MerchantRequestID. Safaricom response: {r}",
        )

    # Check for Safaricom business logic errors (e.g. 1032 = cancelled, 1037 = timeout)
    resp_code = r.get("ResponseCode")
    if resp_code is not None and str(resp_code) != "0":
        resp_desc = r.get("ResponseDescription", "Unknown")
        customer_msg = r.get("CustomerMessage", "")
        logger.warning(
            "STK Push Safaricom business error: ResponseCode=%s, ResponseDescription=%s, CustomerMessage=%s",
            resp_code,
            resp_desc,
            customer_msg,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Safaricom error (ResponseCode {resp_code}): {resp_desc}. CustomerMessage: {customer_msg}",
        )

    # Step 4: Save transaction to DB
    try:
        transaction = StkPushTransaction(
            credential_id=cred.id,
            merchant_request_id=r["MerchantRequestID"],
            checkout_request_id=r["CheckoutRequestID"],
            phone_number=phone_number,
            amount=float(amount),
            account_reference=account_number,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
    except Exception as e:
        logger.exception("STK Push step 4 failed: database save")
        raise HTTPException(status_code=500, detail=f"Failed to save transaction: {str(e)}")

    logger.info(
        "STK Push success: MerchantRequestID=%s, CheckoutRequestID=%s",
        r["MerchantRequestID"],
        r["CheckoutRequestID"],
    )
    return r


@app.post("/callbackurl")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    print("callback has been hit")
    """STK Push callback. Credential resolved from MerchantRequestID+CheckoutRequestID -> StkPushTransaction."""
    raw = await request.json()
    print("raw callback data", raw)
    callback_data = raw.get("Body", {}).get("stkCallback") or raw
    if not isinstance(callback_data, dict):
        raise HTTPException(status_code=400, detail="Invalid callback structure")
    mid = callback_data.get("MerchantRequestID")
    cid = callback_data.get("CheckoutRequestID")
    print("callback", callback_data)
    if not mid or not cid:
        raise HTTPException(status_code=400, detail="Missing MerchantRequestID or CheckoutRequestID")
    transaction = (
        db.query(StkPushTransaction)
        .filter(StkPushTransaction.merchant_request_id == mid, StkPushTransaction.checkout_request_id == cid)
        .first()
    )
    print("transaction", transaction)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    transaction.status = "Done"
    transaction.result_code = callback_data.get("ResultCode")
    transaction.result_desc = callback_data.get("ResultDesc")
    kenya_tz = pytz.timezone("Africa/Nairobi")
    transaction.updated_at = datetime.now(pytz.utc).astimezone(kenya_tz)
    db.commit()
    db.refresh(transaction)
    return {"status": "success", "message": "Callback received successfully"}


# --- C2B ---

@app.post(
    "/mpesa/c2b/registerurl",
    tags=["C2B"],
    summary="Register validation and confirmation URLs on M-Pesa",
)
def register_url(
    payload: RegisterUrlPayload,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    cred = get_credential_for_app(app, payload.credential_id, db)
    base_url = get_base_url(cred.environment)
    token = authenticator(cred.consumer_key, cred.consumer_secret, base_url)
    url = f"{base_url}mpesa/c2b/v2/registerurl"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    body = {
        "ShortCode": cred.business_short_code,
        "ResponseType": "Completed",
        "ConfirmationURL": payload.ConfirmationURL or CALLBACK_URL_CONFIRMATION,
        "ValidationURL": payload.ValidationURL or CALLBACK_URL_VALIDATION,
    }
    r = requests.post(url, json=body, headers=headers).json()
    return r


@app.post("/validationurl", tags=["C2B"])
async def validation_url(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    shortcode = str(body.get("BusinessShortCode") or body.get("ShortCode") or "")
    if shortcode:
        cred = db.query(Credential).filter(Credential.business_short_code == shortcode).first()
        if cred and not cred.is_active:
            pass
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


def _forward_to_app_callback(callback_url: str, body: dict) -> None:
    """Forward Safaricom confirmation payload to app's callback_url. Runs in background."""
    try:
        requests.post(callback_url, json=body, timeout=30)
    except Exception as e:
        logger.warning("Failed to forward to app callback %s: %s", callback_url, e)


@app.post("/confirmationurl", tags=["C2B"])
async def confirmation_url(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.json()
    shortcode = str(body.get("BusinessShortCode") or body.get("ShortCode") or "")
    cred = db.query(Credential).filter(Credential.business_short_code == shortcode).first()
    if not cred:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    try:
        trans_amount = float(body.get("TransAmount", 0))
        txn = Transaction(
            credential_id=cred.id,
            transaction_number=body.get("TransID", ""),
            trans_amount=trans_amount,
            first_name=body.get("FirstName", ""),
            trans_time=str(body.get("TransTime", "")),
            account_reference=body.get("BillRefNumber", ""),
            paybill_no=shortcode,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
    except Exception:
        pass
    try:
        query_transaction_status(cred, body.get("TransID", ""), CALLBACK_URL_RESULT, CALLBACK_URL_TIMEOUT)
    except Exception:
        pass
    # Forward to app callback: first 3 chars of BillRefNumber = account_number
    bill_ref = str(body.get("BillRefNumber", ""))
    if len(bill_ref) >= 3:
        account_number = bill_ref[:3].lower()
        app = db.query(App).filter(App.account_number == account_number).first()
        if app and app.callback_url:
            background_tasks.add_task(_forward_to_app_callback, app.callback_url, body)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@app.post("/resulturl", tags=["C2B"])
async def result_url(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    res = body.get("Result") or {}
    if res.get("ResultCode") != 0:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    params = (res.get("ResultParameters") or {}).get("ResultParameter") or []
    receipt_no = None
    debit_party = None
    for p in params:
        if isinstance(p, dict):
            if p.get("Key") == "ReceiptNo":
                receipt_no = p.get("Value")
            elif p.get("Key") == "DebitPartyName":
                debit_party = p.get("Value")
    if receipt_no:
        txn = db.query(Transaction).filter(Transaction.transaction_number == str(receipt_no)).first()
        if txn and debit_party:
            parts = str(debit_party).split(" - ", 1)
            txn.phone_number = parts[0].strip() if parts else None
            txn.full_name = parts[1].strip() if len(parts) > 1 else None
            db.commit()
            db.refresh(txn)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@app.post("/timeouturl", tags=["C2B"])
async def timeout_url(request: Request):
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


# --- Read APIs ---

@app.get("/transactions/{account_reference}", response_model=Dict[str, List[Dict]])
def get_transactions_by_account_reference(
    account_reference: str,
    credential_id: Optional[str] = None,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    q = db.query(Transaction).join(Credential).filter(
        Transaction.account_reference == account_reference,
        Credential.app_id == app.id,
    )
    if credential_id:
        q = q.filter(Credential.credential_id == credential_id)
    rows = q.all()
    return {
        "transactions": [
            {
                "id": t.id,
                "account_reference": t.account_reference,
                "transaction_number": t.transaction_number,
                "trans_amount": t.trans_amount,
                "first_name": t.first_name,
                "phone_number": t.phone_number,
                "trans_time": t.trans_time,
                "full_name": t.full_name,
                "paybill_no": t.paybill_no,
            }
            for t in rows
        ]
    }


@app.get("/all", response_model=Dict[str, List[Dict]])
def get_transactions_all(
    credential_id: Optional[str] = None,
    db: Session = Depends(get_db),
    app: App = Depends(get_app_from_header),
):
    q = db.query(Transaction).join(Credential).filter(Credential.app_id == app.id)
    if credential_id:
        q = q.filter(Credential.credential_id == credential_id)
    rows = q.all()
    return {
        "transactions": [
            {
                "id": t.id,
                "account_reference": t.account_reference,
                "transaction_number": t.transaction_number,
                "trans_amount": t.trans_amount,
                "first_name": t.first_name,
                "phone_number": t.phone_number,
                "trans_time": t.trans_time,
                "full_name": t.full_name,
                "paybill_no": t.paybill_no,
            }
            for t in rows
        ]
    }
