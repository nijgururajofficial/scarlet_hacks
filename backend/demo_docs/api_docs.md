# AcmeCorp Internal API Documentation
**Version:** 2.4.1 | **Last updated:** March 2025 | **Owner:** Platform Team

---

## Overview

AcmeCorp's backend is a REST API built on FastAPI. All services communicate internally via this API. The base URL for the staging environment is `https://api.staging.acmecorp.internal` and production is `https://api.acmecorp.internal`.

All requests must be authenticated. All responses are JSON. All timestamps are UTC ISO 8601.

---

## Authentication

### API Keys
Internal services use API keys passed as a header:

```
X-API-Key: <your_api_key>
```

API keys are generated per service and per environment. **Never use a production API key in staging or local development.**

To get your development API key:
1. Log in to the AcmeCorp developer portal at `https://dev-portal.acmecorp.internal`
2. Navigate to **Settings → API Keys → Create New Key**
3. Select environment: `development`
4. Copy and store in your `.env` file as `ACME_API_KEY`

Keys expire every 90 days. You will receive an email 7 days before expiry. Rotate immediately — expired keys return `401 Unauthorized`.

### OAuth 2.0 (User-facing endpoints)
User-facing endpoints use OAuth 2.0 with JWT bearer tokens.

```
Authorization: Bearer <jwt_token>
```

JWTs expire after 1 hour. Use the `/auth/refresh` endpoint with the refresh token to get a new access token.

---

## Base URL & Environments

| Environment | Base URL | Notes |
|---|---|---|
| Local | `http://localhost:8000` | Run via Docker Compose |
| Staging | `https://api.staging.acmecorp.internal` | Auto-deploys on merge to `main` |
| Production | `https://api.acmecorp.internal` | Deploy via release tag only |

---

## Core Endpoints

### Users

#### `GET /v2/users/{user_id}`
Returns a user object by ID.

**Headers:** `X-API-Key` required

**Response:**
```json
{
  "id": "usr_a1b2c3",
  "email": "jane@acmecorp.com",
  "name": "Jane Smith",
  "role": "admin",
  "created_at": "2024-01-15T09:00:00Z",
  "is_active": true
}
```

**Error codes:**
- `404` — User not found
- `401` — Invalid or missing API key

---

#### `POST /v2/users`
Creates a new user. Used by the onboarding flow.

**Body:**
```json
{
  "email": "newuser@acmecorp.com",
  "name": "New User",
  "role": "viewer"
}
```

**Roles:** `admin`, `editor`, `viewer`

**Response:** `201 Created` with user object.

**Notes:** Triggers a welcome email automatically via the notification service. Do not call the email service directly.

---

#### `PATCH /v2/users/{user_id}`
Updates user fields. Partial updates supported — only send fields you want to change.

**Notes:** Updating `role` to `admin` requires the calling service to itself have `admin` scope. Otherwise returns `403 Forbidden`.

---

#### `DELETE /v2/users/{user_id}`
Soft-deletes a user. Sets `is_active: false`. Data is retained for 90 days per compliance policy before hard deletion.

---

### Projects

#### `GET /v2/projects`
Returns a paginated list of projects the authenticated user has access to.

**Query params:**
- `page` (int, default 1)
- `limit` (int, default 20, max 100)
- `status` (string: `active`, `archived`, `all`)

**Response:**
```json
{
  "data": [...],
  "total": 142,
  "page": 1,
  "limit": 20
}
```

---

#### `POST /v2/projects`
Creates a new project.

**Body:**
```json
{
  "name": "My Project",
  "description": "Optional description",
  "owner_id": "usr_a1b2c3"
}
```

**Notes:** `owner_id` defaults to the calling user if omitted. Every project gets a `project_id` prefixed with `proj_`.

---

#### `POST /v2/projects/{project_id}/members`
Adds a member to a project.

**Body:**
```json
{
  "user_id": "usr_a1b2c3",
  "role": "editor"
}
```

---

### Billing

#### `GET /v2/billing/subscriptions/{org_id}`
Returns the current subscription for an organisation.

**Notes:** Only callable by services with `billing` scope. If your service needs billing data, request the scope via `#platform-team` on Slack before coding — billing endpoints require a security review.

---

### Webhooks

#### `POST /v2/webhooks`
Registers a webhook endpoint to receive event notifications.

**Supported events:**
- `user.created`
- `user.deleted`
- `project.created`
- `project.archived`
- `billing.invoice.paid`
- `billing.subscription.cancelled`

**Body:**
```json
{
  "url": "https://your-service.internal/webhooks",
  "events": ["user.created", "project.created"],
  "secret": "your_signing_secret"
}
```

All webhook payloads are signed with HMAC-SHA256. Verify the signature using the `X-Acme-Signature` header before processing. See `docs/webhooks-security.md` for the verification implementation.

---

## Error Handling

All errors follow this structure:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "User with id usr_xyz does not exist",
    "request_id": "req_abc123"
  }
}
```

Always log `request_id` when reporting bugs — it's the fastest way to trace issues in our logging system (Datadog).

**Standard error codes:**

| HTTP Status | Code | Meaning |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Bad request body or params |
| 401 | `UNAUTHORIZED` | Missing or invalid API key / token |
| 403 | `FORBIDDEN` | Valid auth but insufficient permissions |
| 404 | `RESOURCE_NOT_FOUND` | Entity does not exist |
| 409 | `CONFLICT` | Duplicate resource (e.g. email already exists) |
| 422 | `UNPROCESSABLE` | Request understood but semantically invalid |
| 429 | `RATE_LIMITED` | Too many requests — back off and retry |
| 500 | `INTERNAL_ERROR` | Something went wrong on our side — include request_id when reporting |

---

## Rate Limits

| Tier | Limit |
|---|---|
| Default (internal services) | 1000 req/min |
| Billing endpoints | 100 req/min |
| Auth endpoints | 30 req/min |

Rate limit headers are returned on every response:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1711234567
```

On `429`, wait until `X-RateLimit-Reset` before retrying. Use exponential backoff for retry logic. Never hammer a 429 in a tight loop — it will get your key temporarily banned.

---

## Pagination

All list endpoints use cursor-based pagination. Prefer `cursor` over `page` for large datasets — page-based pagination is deprecated and will be removed in v3.

```
GET /v2/projects?cursor=eyJpZCI6MTIzfQ&limit=20
```

Response includes:
```json
{
  "data": [...],
  "next_cursor": "eyJpZCI6MTQzfQ",
  "has_more": true
}
```

---

## Versioning

The current stable version is `v2`. Version `v1` is deprecated and will be sunset on **1 September 2025**. If you see any `v1` calls in the codebase, migrate them — there's a tracking issue in Linear.

Breaking changes are announced in `#engineering` on Slack at least 4 weeks before release.

---

## Local Development

### Setup
```bash
git clone git@github.com:acmecorp/api.git
cd api
cp .env.example .env      # fill in your dev API key
docker-compose up         # starts API + postgres + redis
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs` (Swagger UI).

### Running tests
```bash
pytest                    # run all tests
pytest tests/unit         # unit tests only
pytest -k "test_users"    # filter by name
```

Test coverage must stay above 80%. PRs that drop coverage will fail CI.

### Seeding the database
```bash
python scripts/seed_db.py --env development
```

This creates 10 test users, 5 projects, and sample billing data. Seed data is reset every night in staging automatically.

---

## SDK

An internal Python SDK is available for server-to-server calls:

```bash
pip install acmecorp-sdk --index-url https://pypi.acmecorp.internal
```

```python
from acmecorp import AcmeClient

client = AcmeClient(api_key="your_key", env="staging")
user = client.users.get("usr_a1b2c3")
projects = client.projects.list(status="active")
```

Prefer the SDK over raw HTTP calls for new internal services. It handles retries, rate limiting, and auth token refresh automatically.

---

## Contact

| Topic | Contact |
|---|---|
| API bugs / incidents | `#platform-team` on Slack or page via PagerDuty |
| New scope requests | Post in `#platform-team` with your use case |
| SDK issues | Open issue in `github.com/acmecorp/acmecorp-sdk` |
| Billing endpoint access | DM **Sarah Chen** (Platform Lead) |
