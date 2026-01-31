import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


def generate_api_key() -> str:
    return uuid.uuid4().hex


def generate_credential_id() -> str:
    return uuid.uuid4().hex


class App(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Credential(Base):
    """M-Pesa paybill/till credentials under an app."""
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False, index=True)
    credential_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    consumer_key = Column(String(255), nullable=False)
    consumer_secret = Column(String(255), nullable=False)
    business_short_code = Column(String(32), nullable=False, index=True)
    passkey = Column(String(255), nullable=False)
    initiator_name = Column(String(64), nullable=False)
    security_credential = Column(Text, nullable=False)
    environment = Column(String(16), nullable=False, default="production")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StkPushTransaction(Base):
    __tablename__ = "stk_push_transactions"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=False, index=True)
    merchant_request_id = Column(String(255), nullable=False, index=True)
    checkout_request_id = Column(String(255), nullable=False, index=True)
    phone_number = Column(String(32), nullable=False)
    account_reference = Column(String(64), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(32), default="Pending")
    result_code = Column(Integer, nullable=True)
    result_desc = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "paybill_offline"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=False, index=True)
    account_reference = Column(String(64), nullable=False)
    transaction_number = Column(String(64), nullable=False)
    trans_amount = Column(Float, nullable=False)
    first_name = Column(String(128), nullable=False)
    phone_number = Column(String(32), nullable=True)
    trans_time = Column(String(32), nullable=False)
    full_name = Column(String(255), nullable=True)
