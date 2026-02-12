# Pokant API Documentation

Base URL: `https://api.pokant.com` (or `http://localhost:8000` for dev)

## Authentication

Include your API token in the `Authorization` header:

```
Authorization: Bearer pk_your_token_here
```

- Tokens are returned **once** when you onboard a customer via `POST /api/onboard`.
- Store the token securely; it cannot be retrieved again.
- Use it for programmatic access to protected endpoints (when implemented).

## Endpoints

### Health & monitoring

- **GET /health** – Health check (database + Redis). Returns 200 when healthy, 503 when database is down.
- **GET /metrics** – Prometheus metrics (if `prometheus-client` is installed).

### Onboarding

- **POST /api/onboard** – Create a new customer and start analysis.
  - Body: `CustomerCreate` (company_name, email, bot_provider, bot_id?, vapi_api_key?, retell_api_key?).
  - Returns: `customer_id`, `api_token` (save it), `status`, `message`.
  - Triggers background analysis (Celery); check back in 5–10 minutes.

### Dashboard

- **GET /api/dashboard/{customer_id}** – Dashboard stats (calls, success rate, trends). Falls back to mock data if no calls.

### Patterns & variants

- **GET /api/patterns/{customer_id}** – List failure patterns for a customer.
- **GET /api/variants/{pattern_id}** – Get (or generate) 5 prompt variants for a pattern.
- **POST /api/variants/{pattern_id}/regenerate** – Regenerate variants.
- **GET /api/variants/detail/{variant_id}** – Get a single variant.

### A/B tests

- **POST /api/tests/deploy** – Deploy an A/B test.
- **GET /api/tests/{test_id}** – Get test status and results.

## Errors

- **422** – Validation error (body/query invalid). Response includes `details` with field-level errors.
- **401** – Invalid or missing API token (on protected routes).
- **404** – Resource not found (e.g. pattern_id or variant_id).
- **500** – Server error. In debug mode, `detail` may include the exception message.

## Running locally

```bash
# With Docker
docker-compose up -d db redis
docker-compose up backend

# Celery worker (optional, for background analysis)
docker-compose up celery celery-beat
```

## Pilot checklist

1. Set `ENCRYPTION_KEY` (use `python -c "from app.services.encryption import generate_key; print(generate_key())"`).
2. Set `CLAUDE_API_KEY` and `OPENAI_API_KEY` for analysis and variant generation.
3. Create a test customer via `POST /api/onboard` and save the `api_token`.
4. Use the dashboard and variants endpoints with the returned `customer_id`.
