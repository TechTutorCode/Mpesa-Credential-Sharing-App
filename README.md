# M-Pesa Credential Sharing App

Multi-tenant M-Pesa API proxy. Register apps, then register paybills under each app. All requests use **api_key** in the header; routes that need a specific paybill use **credential_id** in the body.

## Authentication: How to attach the API key

Include your `api_key` in **every request** (except `POST /apps` and callbacks) using one of these headers:

| Header | Example |
|--------|---------|
| `X-API-Key` | `X-API-Key: a1b2c3d4e5f6...` |
| `Authorization` | `Authorization: Bearer a1b2c3d4e5f6...` |

**Swagger UI (interactive docs):**
1. Open `http://localhost:8000/docs`
2. Click the **Authorize** button (lock icon at the top right)
3. Enter your `api_key` in the **X-API-Key** field
4. Click **Authorize**, then **Close**
5. All requests will now include the API key automatically

**cURL example:**
```bash
curl -X POST "http://localhost:8000/stkpush" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"credential_id": "...", "phoneNumber": "254712345678", "accountNumber": "ACC001", "amount": 100}'
```

**JavaScript (fetch) example:**
```javascript
fetch("http://localhost:8000/stkpush", {
  method: "POST",
  headers: {
    "X-API-Key": "YOUR_API_KEY",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    credential_id: "YOUR_CREDENTIAL_ID",
    phoneNumber: "254712345678",
    accountNumber: "ACC001",
    amount: 100
  })
});
```

## Flow

1. **Register app** → `POST /apps` with `{ "name": "My App", "callback_url": "https://yourapp.com/mpesa/callback" }` → returns `account_number` (3-letter, unique), `api_key`, `callback_url`
2. **Register paybill** → `POST /paybills` with `X-API-Key` + paybill credentials → returns `credential_id` (auto-generated)
3. **STK push, C2B register, etc.** → `X-API-Key` in header + `credential_id` in body (where applicable)

## Setup

1. Copy `.env.example` to `.env` and set `DATABASE_URL`, `APP_BASE_URL`
2. Run: `pip install -r requirements.txt && uvicorn main:app --reload`

**PostgreSQL:** Set `DATABASE_URL=postgresql://user:password@host:port/database`. Create the database first (e.g. `createdb mpesa_sharing`). Tables are created automatically on first run.

**Note:** If upgrading from an older schema, use a new `DATABASE_URL` or drop/recreate the database so tables are created fresh.

## Endpoints

| Method | Path | Auth | Body | Description |
|--------|------|------|------|-------------|
| POST | `/apps` | — | `{ "name": "...", "callback_url": "https://..." }` | Register app. Returns `name`, `account_number` (3-letter, unique), `api_key`, `callback_url`, `created_at`, `updated_at` |
| PATCH | `/apps` | X-API-Key | `{ "name"?, "callback_url"? }` | Update the authenticated app. Only provided fields are updated. |
| GET | `/paybills` | X-API-Key | — | List all paybills for the app. |
| POST | `/paybills` | X-API-Key | name, consumer_key, consumer_secret, business_short_code, passkey, initiator_name, security_credential, environment | Register paybill under app. Returns `credential_id`, `name`, `business_short_code`, `environment`, `created_at`, `updated_at` |
| PATCH | `/paybills/{credential_id}` | X-API-Key | name?, consumer_key?, consumer_secret?, business_short_code?, passkey?, initiator_name?, security_credential?, environment?, is_active? | Update paybill. Only provided fields are updated. |
| POST | `/stkpush` | X-API-Key | `{ "credential_id", "phoneNumber", "accountNumber", "amount", "transactionDescription?" }` | Initiate STK push |
| POST | `/mpesa/c2b/registerurl` | X-API-Key | `{ "credential_id", "ConfirmationURL?", "ValidationURL?" }` | Register C2B URLs for paybill |
| GET | `/transactions/{account_reference}` | X-API-Key | — | Get C2B transactions. Optional `?credential_id=` to filter |
| GET | `/all` | X-API-Key | — | Get all C2B transactions. Optional `?credential_id=` to filter |

Callbacks (M-Pesa → your app, no auth): `/callbackurl`, `/validationurl`, `/confirmationurl`, `/resulturl`, `/timeouturl`

## Examples

### 1. Register app

```bash
curl -X POST "http://localhost:8000/apps" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme", "callback_url": "https://acme.com/mpesa/callback"}'
```

Response: `{ "name": "Acme", "account_number": "xyz", "api_key": "a1b2c3d4e5f6...", "callback_url": "https://acme.com/mpesa/callback", "created_at": "...", "updated_at": "..." }`

**C2B forwarding:** When `/confirmationurl` receives a Safaricom confirmation, it forwards the full request to the app's `callback_url` if the first 3 letters of `BillRefNumber` match an app's `account_number`. Customers should use `{account_number}{reference}` (e.g. `xyz123`) as the account reference when paying.

### 2. Register paybill (use api_key from step 1)

```bash
curl -X POST "http://localhost:8000/paybills" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Paybill",
    "consumer_key": "...",
    "consumer_secret": "...",
    "business_short_code": "174379",
    "passkey": "...",
    "initiator_name": "AcmeAPI",
    "security_credential": "<from encryptpass.py>",
    "environment": "sandbox"
  }'
```

Response: `{ "credential_id": "abc123...", "name": "Acme Paybill", "business_short_code": "174379", "environment": "sandbox", "created_at": "...", "updated_at": "..." }`

### 3. STK push (use api_key and credential_id)

```bash
curl -X POST "http://localhost:8000/stkpush" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "credential_id": "YOUR_CREDENTIAL_ID",
    "phoneNumber": "254712345678",
    "accountNumber": "ACC001",
    "amount": 100
  }'
```

### 4. C2B register URL

```bash
curl -X POST "http://localhost:8000/mpesa/c2b/registerurl" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"credential_id": "YOUR_CREDENTIAL_ID"}'
```
