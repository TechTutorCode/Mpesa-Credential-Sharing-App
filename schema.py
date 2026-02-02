from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- App registration ---

class RegisterAppRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    callback_url: str = Field(..., min_length=1, max_length=512)


class RegisterAppResponse(BaseModel):
    name: str
    account_number: str
    api_key: str
    callback_url: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateAppRequest(BaseModel):
    """All fields optional for partial update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    callback_url: Optional[str] = Field(None, min_length=1, max_length=512)


# --- Paybill registration (same as old MpesaCredentialCreate except no api_key) ---

class RegisterPaybillRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    consumer_key: str
    consumer_secret: str
    business_short_code: str
    passkey: str
    initiator_name: str
    security_credential: str
    environment: str = "production"


class RegisterPaybillResponse(BaseModel):
    credential_id: str
    name: str
    business_short_code: str
    environment: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdatePaybillRequest(BaseModel):
    """All fields optional for partial update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    business_short_code: Optional[str] = None
    passkey: Optional[str] = None
    initiator_name: Optional[str] = None
    security_credential: Optional[str] = None
    environment: Optional[str] = None
    is_active: Optional[bool] = None


# --- STK Push (api_key in header, credential_id in body) ---

class STKResponse(BaseModel):
    MerchantRequestID: str
    CheckoutRequestID: str
    ResponseCode: int
    ResponseDescription: str
    CustomerMessage: str


class STKPushPayload(BaseModel):
    credential_id: str
    amount: int
    phoneNumber: str = Field(..., min_length=1, max_length=12)
    accountNumber: str = Field(..., min_length=1, max_length=12)
    transactionDescription: Optional[str] = Field(None, min_length=1, max_length=13)


class MpesacallbackResponse(BaseModel):
    MerchantRequestID: str
    CheckoutRequestID: str
    ResultCode: int
    ResultDesc: str
    Amount: float
    MpesaReceiptNumber: str
    PhoneNumber: str


# --- C2B ---

class RegisterUrlPayload(BaseModel):
    credential_id: str
    ConfirmationURL: Optional[str] = None
    ValidationURL: Optional[str] = None
