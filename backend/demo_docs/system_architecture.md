# AcmeCorp System Architecture & Tech Stack
**Version:** 1.8 | **Last updated:** January 2025 | **Owner:** Marcus Webb (DevOps / Infra)

This document is the reference for AcmeCorp's infrastructure, cloud setup, internal services, and tech stack. Read this before touching anything in AWS or asking "what do we use for X."

---

## Cloud Provider

**Primary:** Amazon Web Services (AWS) — `us-east-1` (primary), `eu-west-1` (EU data residency for GDPR compliance)

**Account structure:**
| Account | Purpose |
|---|---|
| `acmecorp-dev` | Developer sandboxes, local testing infra |
| `acmecorp-staging` | Staging environment, auto-deploys from `main` |
| `acmecorp-prod` | Production — restricted access |
| `acmecorp-infra` | Shared infra: ECR, Route53, ACM certificates |

Access to `acmecorp-prod` is read-only for most engineers. Write access requires manager approval — request via `#it-help`.

---

## Core Infrastructure

### Compute
| Service | AWS Service | Notes |
|---|---|---|
| API backend | ECS Fargate | Containerised, auto-scaling, no EC2 to manage |
| Background workers | ECS Fargate (separate task def) | Celery workers for async jobs |
| Cron jobs | AWS EventBridge + Lambda | Lightweight scheduled tasks only |
| Frontend (web app) | Vercel | Deployed independently from backend |

### Networking
- **VPC:** Custom VPC per environment with public/private subnets
- **Load balancer:** AWS ALB (Application Load Balancer) in front of all ECS services
- **DNS:** Route53 — all `*.acmecorp.internal` domains resolve inside the VPC
- **CDN:** CloudFront for static assets and the marketing site
- **SSL:** ACM (AWS Certificate Manager) — certificates auto-renew

---

## Databases

### Primary Database — PostgreSQL
- **Service:** AWS RDS PostgreSQL 15 (Multi-AZ in production)
- **ORM:** SQLAlchemy (Python)
- **Migrations:** Alembic — run migrations before deploying new code
- **Backups:** Automated daily snapshots, retained 30 days
- **Connection pooling:** PgBouncer sits between the app and RDS

```bash
# Connect to staging DB (read-only)
psql $STAGING_DB_URL

# Run migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "add_index_to_users_email"
```

**Production DB access:** Read-only requires a request in `#data-access`. Write access is restricted to migration runs during deploys only — no direct prod DB writes outside of migrations.

### Cache — Redis
- **Service:** AWS ElastiCache (Redis 7)
- **Used for:** Session storage, rate limiting counters, short-lived feature flags, job queues (via Celery)
- **TTL policy:** All keys must have a TTL set — no persistent Redis keys (Redis is not a database)
- **Client:** `redis-py` in Python services

### Search — Elasticsearch
- **Service:** AWS OpenSearch (managed Elasticsearch 8 compatible)
- **Used for:** Full-text search across projects and user content
- **Index management:** Handled by the Platform team — don't create or delete indices without talking to **Sarah Chen**
- **Client:** `elasticsearch-py`

### Object Storage — S3
- **Service:** AWS S3
- **Buckets:**
  - `acmecorp-uploads-{env}` — user file uploads
  - `acmecorp-assets-{env}` — processed/transformed assets
  - `acmecorp-backups` — DB snapshots and data exports (prod only)
- **Access:** All S3 access goes through pre-signed URLs — never expose a bucket publicly or generate permanent credentials for client-side access

---

## Message Queue & Async Jobs

### Queue — SQS + Celery
- **Service:** AWS SQS (Simple Queue Service)
- **Task runner:** Celery with SQS as the broker
- **Used for:** Email sending, webhook delivery, report generation, data exports, billing sync

```python
# Dispatching a background task
from app.tasks import send_welcome_email
send_welcome_email.delay(user_id="usr_a1b2c3")
```

- **Dead letter queue (DLQ):** Failed tasks after 3 retries go to DLQ. Monitor in `#alerts` Slack channel or Datadog.
- **Priority queues:** `high`, `default`, `low` — billing and auth tasks use `high`, email uses `low`

### Event Streaming — SNS
- **Service:** AWS SNS (Simple Notification Service)
- **Used for:** Fan-out events to multiple consumers (e.g. `user.created` notifies billing service, email service, and analytics simultaneously)
- **Pattern:** Services subscribe to SNS topics, not to each other directly — loose coupling

---

## Backend Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Language | Python | 3.11 | Type hints required on all new code |
| Web framework | FastAPI | 0.110 | Async-first, OpenAPI docs auto-generated |
| ORM | SQLAlchemy | 2.0 | Use async sessions for new code |
| Task queue | Celery | 5.3 | SQS broker in all environments |
| HTTP client | httpx | 0.27 | Async-compatible, prefer over requests |
| Validation | Pydantic | v2 | All request/response models |
| Auth | python-jose | 3.3 | JWT handling |
| Testing | pytest | 8.x | + pytest-asyncio for async tests |
| Linting | Ruff | 0.4 | Replaces flake8 + isort + black |
| Type checking | mypy | 1.9 | Run in CI — must pass |

### Python conventions
- All new endpoints must be `async def`
- Use Pydantic models for all request bodies and responses — no raw dicts in controllers
- Business logic lives in `services/`, not in route handlers
- Route handlers should be thin: validate input, call a service, return response

---

## Frontend Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Framework | React 18 | TypeScript only |
| Build tool | Vite | Fast dev server + production builds |
| Styling | Tailwind CSS | No custom CSS files — use utility classes |
| State management | Zustand | Lightweight, no Redux |
| Data fetching | TanStack Query | Caching, background refresh, optimistic updates |
| Component library | Radix UI | Accessible primitives, unstyled |
| Forms | React Hook Form + Zod | Schema validation on client side |
| Testing | Vitest + React Testing Library | |
| Deployment | Vercel | Automatic previews on every PR |

Frontend repo: `github.com/acmecorp/frontend` — separate from the API repo.

---

## CI/CD Pipeline

**Platform:** GitHub Actions

### Pipeline stages (backend)
1. **Lint** — `ruff check .` + `mypy` (2 min)
2. **Test** — `pytest` with coverage check ≥80% (4 min)
3. **Build** — Docker image built and pushed to ECR (3 min)
4. **Deploy staging** — ECS service updated (2 min) — runs on merge to `main`
5. **Deploy production** — runs on git tag push only

### Pipeline stages (frontend)
1. **Lint** — ESLint + TypeScript check
2. **Test** — Vitest
3. **Deploy preview** — Vercel preview URL on every PR
4. **Deploy production** — Vercel production on merge to `main`

Pipelines are defined in `.github/workflows/`. Don't edit pipeline files without discussing with **Marcus Webb**.

---

## Observability Stack

### Logging
- **Service:** Datadog Logs
- **Format:** Structured JSON logs — never use `print()` in production code
- **Logger setup:**
```python
import structlog
log = structlog.get_logger()
log.info("user_created", user_id=user.id, email=user.email)
```
- Always include `request_id` in logs for traceability
- Log levels: `DEBUG` (local only), `INFO` (normal ops), `WARNING` (unexpected but handled), `ERROR` (needs attention)

### Metrics & APM
- **Service:** Datadog APM + custom metrics
- **Dashboards:** `app.datadoghq.com` — ask **Marcus Webb** for access
- **Key dashboards:** API latency, error rates, queue depth, DB connection pool usage
- **Alerting:** PagerDuty integration — critical alerts page on-call engineer immediately

### Error Tracking
- **Service:** Sentry
- **Setup:** Auto-configured via `sentry-sdk` — exceptions are captured automatically
- **Project:** `acmecorp-api` in Sentry — accessible at `sentry.io/acmecorp`
- All unhandled exceptions appear in `#alerts` Slack channel

### Uptime Monitoring
- **Service:** AWS CloudWatch + Datadog Synthetics
- **SLO:** 99.9% uptime for production API
- **Status page:** `status.acmecorp.com` (public-facing)

---

## Security & Secrets Management

### Secrets
- **Service:** AWS Secrets Manager
- **Rule:** No secrets in code, `.env` files committed to git, or Slack messages — ever
- **Local dev:** `.env` file (gitignored) — copy from `.env.example` and fill in dev values from 1Password
- **Production:** Secrets injected as environment variables at container startup from Secrets Manager

### Dependency scanning
- **Dependabot** runs weekly — auto-creates PRs for security patches
- Critical CVEs must be patched within 48 hours
- Non-critical within the next sprint

### Network security
- All internal services communicate within the VPC — nothing exposed to the public internet except the ALB
- Security groups follow least-privilege — services only have access to what they need
- WAF (AWS Web Application Firewall) sits in front of the ALB in production

---

## Third-Party Services

| Service | Purpose | Owner |
|---|---|---|
| Stripe | Payment processing, subscriptions | **Sarah Chen** (Platform) |
| SendGrid | Transactional email | **Aaliya Torres** |
| Twilio | SMS notifications (optional feature) | **Aaliya Torres** |
| Auth0 | User authentication (SSO, social login) | **David Kim** |
| Segment | Product analytics event pipeline | **Priya Nair** (EM) |
| LaunchDarkly | Feature flags | **David Kim** |
| PagerDuty | On-call alerting | **Marcus Webb** |
| Sentry | Error tracking | **Marcus Webb** |
| Datadog | Monitoring, APM, logs | **Marcus Webb** |
| Vercel | Frontend hosting | **David Kim** |
| GitHub | Source control, CI/CD | **Marcus Webb** |
| Linear | Issue tracking | **Priya Nair** |
| 1Password | Secrets / credential management | IT Team |

To get access to any third-party service, post in `#it-help` with your justification. Most are provisioned same-day.

---

## Service Map

```
Internet
    │
    ▼
CloudFront (CDN / static assets)
    │
    ▼
ALB (Load Balancer)
    │
    ├──► ECS Fargate (API — FastAPI)
    │         │
    │         ├──► RDS PostgreSQL (primary DB)
    │         ├──► ElastiCache Redis (cache + sessions)
    │         ├──► OpenSearch (full-text search)
    │         └──► SQS (task queue)
    │                   │
    │                   ▼
    │             ECS Fargate (Celery workers)
    │                   │
    │                   ├──► SendGrid (email)
    │                   ├──► Stripe (billing)
    │                   └──► S3 (file storage)
    │
    └──► Vercel (Frontend — React)
```

---

## Contacts & Ownership

| Area | Owner | Slack |
|---|---|---|
| AWS infrastructure | Marcus Webb | @marcus.webb |
| CI/CD pipelines | Marcus Webb | @marcus.webb |
| Database / migrations | Sarah Chen | @sarah.chen |
| Third-party integrations | David Kim | @david.kim |
| Feature flags (LaunchDarkly) | David Kim | @david.kim |
| Frontend / Vercel | David Kim | @david.kim |
| Monitoring / Datadog | Marcus Webb | @marcus.webb |
| Security incidents | Priya Nair | @priya.nair |
