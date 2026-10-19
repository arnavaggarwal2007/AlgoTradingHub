# API Documentation

JSON API for programmatic access to Pre-Swing Trade signals and data.

---

## 🔑 Authentication

All API requests require an API key in the header:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/signals
```

### Getting Your API Key

1. Log in to the dashboard
2. Go to Settings → API Keys
3. Click "Generate New Key"
4. Copy and save (shown only once!)

---

## 📊 Endpoints

### GET `/api/v1/signals`
Fetch latest pre-swing reversal signals.

**Query Parameters:**
- `limit` (int, default: 100) — Max results
- `offset` (int, default: 0) — Pagination
- `filter` (string) — "uptrend", "pullback", "strong_uptrend"

**Example:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://yourdomain.com/api/v1/signals?limit=50&filter=uptrend"
```

**Response (200 OK):**
```json
{
  "data": [
    {
      "symbol": "NVDA",
      "signal_type": "EMA21_Touch",
      "market_state": "UPTREND",
      "entry_price": 140.50,
      "target1": 150.55,
      "target2": 155.10,
      "target3": 159.65,
      "stop_loss": 128.00,
      "signal_strength": 0.85,
      "timestamp": "2025-02-22T10:30:00Z"
    },
    ...
  ],
  "pagination": {
    "total": 45,
    "limit": 50,
    "offset": 0
  }
}
```

---

### GET `/api/v1/signals/{symbol}`
Fetch signals for a specific stock.

**Example:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/signals/AAPL
```

**Response (200 OK):**
```json
{
  "symbol": "AAPL",
  "current_price": 195.30,
  "signals": [
    {
      "signal_type": "Engulfing",
      "market_state": "PULLBACK_SETUP",
      "entry_price": 194.50,
      ...
    }
  ],
  "technical_levels": {
    "ema21": 192.10,
    "sma50": 188.50,
    "sma200": 185.20,
    "rsi": 52.3,
    "atr": 3.20
  }
}
```

---

### POST `/api/v1/backtest`
Run a backtest on a strategy.

**Request Body:**
```json
{
  "symbol": "AAPL",
  "start_date": "2024-01-01",
  "end_date": "2025-02-22",
  "strategy": "v67",
  "initial_capital": 10000
}
```

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","start_date":"2024-01-01","end_date":"2025-02-22"}' \
  https://yourdomain.com/api/v1/backtest
```

**Response (200 OK):**
```json
{
  "symbol": "AAPL",
  "total_return": 0.24,
  "win_rate": 0.68,
  "sharpe_ratio": 1.45,
  "max_drawdown": -0.12,
  "trades": [
    {
      "entry_date": "2024-01-15",
      "entry_price": 140.50,
      "exit_date": "2024-01-22",
      "exit_price": 149.50,
      "pnl": 9.00,
      "pnl_pct": 0.064
    }
  ]
}
```

---

### GET `/api/v1/watchlist`
Get your current watchlist.

**Example:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/watchlist
```

**Response (200 OK):**
```json
{
  "symbols": ["NVDA", "TSLA", "AAPL", "MSFT"],
  "count": 4
}
```

---

### POST `/api/v1/watchlist`
Add a symbol to your watchlist.

**Request Body:**
```json
{
  "symbol": "GOOGL"
}
```

**Response (201 Created):**
```json
{
  "message": "GOOGL added to watchlist",
  "symbols": ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL"]
}
```

---

### DELETE `/api/v1/watchlist/{symbol}`
Remove a symbol from watchlist.

**Example:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/watchlist/NVDA
```

**Response (200 OK):**
```json
{
  "message": "NVDA removed from watchlist",
  "symbols": ["TSLA", "AAPL", "MSFT", "GOOGL"]
}
```

---

### GET `/api/v1/account`
Get your account info.

**Example:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/account
```

**Response (200 OK):**
```json
{
  "email": "user@example.com",
  "subscription_tier": "premium",
  "subscription_renews": "2025-03-22",
  "api_calls_this_month": 450,
  "api_limit": 5000,
  "created_at": "2025-01-01",
  "last_login": "2025-02-22T10:30:00Z"
}
```

---

## 🔄 Webhooks (Premium Only)

Subscribe to real-time signal notifications.

### Create Webhook
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook",
    "events": ["signal_generated", "signal_alert"]
  }' \
  https://yourdomain.com/api/v1/webhooks
```

### Receive Webhook Event
When a new signal is generated:
```json
{
  "event": "signal_generated",
  "timestamp": "2025-02-22T10:30:00Z",
  "data": {
    "symbol": "NVDA",
    "signal_type": "EMA21_Touch",
    "entry_price": 140.50,
    ...
  }
}
```

---

## ⚠️ Rate Limits

### Free Tier
- 100 requests/hour
- Historical data: 90 days

### Premium Tier
- 1000 requests/hour
- Historical data: 2 years
- Real-time signals
- Webhooks

### API Tier
- 5000 requests/hour
- Unlimited historical data
- Multiple concurrent connections
- Priority support

---

## 🔁 Pagination

All list endpoints support pagination:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://yourdomain.com/api/v1/signals?limit=20&offset=40"
```

Response includes:
```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 40,
    "has_more": true
  }
}
```

---

## ❌ Error Handling

### 400 Bad Request
```json
{
  "error": "Invalid symbol",
  "message": "Symbol must be 1-5 characters"
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "API key is missing or invalid"
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limited",
  "message": "You have exceeded 1000 requests/hour",
  "retry_after": 3600
}
```

### 500 Server Error
```json
{
  "error": "Internal server error",
  "message": "Something went wrong. Try again later."
}
```

---

## 💻 Code Examples

### Python
```python
import requests

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://yourdomain.com/api/v1"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Get signals
response = requests.get(f"{BASE_URL}/signals", headers=headers)
signals = response.json()

# Run backtest
backtest_data = {
    "symbol": "AAPL",
    "start_date": "2024-01-01",
    "end_date": "2025-02-22"
}
response = requests.post(
    f"{BASE_URL}/backtest",
    json=backtest_data,
    headers=headers
)
results = response.json()
```

### JavaScript
```javascript
const API_KEY = "YOUR_API_KEY";
const BASE_URL = "https://yourdomain.com/api/v1";

async function getSignals() {
  const response = await fetch(`${BASE_URL}/signals`, {
    headers: {
      "Authorization": `Bearer ${API_KEY}`
    }
  });
  return await response.json();
}

async function runBacktest(symbol) {
  const response = await fetch(`${BASE_URL}/backtest`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      symbol,
      start_date: "2024-01-01",
      end_date: "2025-02-22"
    })
  });
  return await response.json();
}
```

### cURL
```bash
# Get signals
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://yourdomain.com/api/v1/signals

# Run backtest
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","start_date":"2024-01-01"}' \
  https://yourdomain.com/api/v1/backtest
```

---

## 📞 Support

Email: api-support@yourdomain.com
Docs: https://docs.yourdomain.com
Status: https://status.yourdomain.com
