# AcmeCorp Engineering Handbook
**Last updated:** February 2025 | **Owner:** Engineering Leadership

Welcome to the team. This handbook covers how we work — our process, tools, expectations, and culture. Read this in your first week. Bookmark it. Things change, so check back occasionally.

---

## Getting Started — First Week Checklist

### Day 1
- [ ] Get laptop from IT (Slack: **#it-help**)
- [ ] Set up 1Password — all credentials go here, nothing in Slack or email
- [ ] Accept GitHub org invite (`github.com/acmecorp`) — ask your manager if you don't receive it
- [ ] Join Slack workspace — invite sent to your work email
- [ ] Set up local dev environment (see Dev Setup below)
- [ ] Get your development API key from `https://dev-portal.acmecorp.internal`
- [ ] Join mandatory Slack channels (list below)
- [ ] Meet your onboarding buddy — assigned by your manager on day 1

### Day 2–3
- [ ] Complete security training in Rippling (mandatory, must finish by day 5)
- [ ] Request access to staging environment — ask in `#platform-team`
- [ ] Read the API docs (`/docs/api_docs.md`)
- [ ] Shadow a team standup and a sprint planning session
- [ ] Set up Datadog access — ask **Marcus Webb** (DevOps)

### Week 1
- [ ] Complete your first small ticket (your manager will assign one labelled `good-first-issue`)
- [ ] Open your first PR (even if it's a small fix)
- [ ] 1:1 with your manager — scheduled by them
- [ ] Meet with Platform Lead (**Sarah Chen**) for a systems overview
- [ ] Review open Linear issues for your squad

---

## Dev Environment Setup

### Requirements
- macOS 13+ or Ubuntu 22.04
- Docker Desktop 4.x
- Python 3.11+
- Node.js 20+ (for frontend services)
- Git 2.39+

### Steps
```bash
# 1. Clone the main API repo
git clone git@github.com:acmecorp/api.git
cd api

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Fill in ACME_API_KEY with your dev key from the developer portal

# 4. Start services
docker-compose up

# 5. Verify
curl http://localhost:8000/health
# Should return {"status": "ok"}
```

Interactive API docs available at `http://localhost:8000/docs` once running.

For frontend services:
```bash
cd frontend
npm install
npm run dev   # starts on http://localhost:3000
```

If you hit any setup issues, post in `#dev-help` on Slack with your error message. Don't spend more than 30 minutes stuck on setup before asking.

---

## Git Conventions

### Branch naming
```
feature/<ticket-id>-short-description
fix/<ticket-id>-short-description
chore/<ticket-id>-short-description
hotfix/<ticket-id>-short-description
```

Examples:
- `feature/ACM-412-add-webhook-retry`
- `fix/ACM-389-user-deletion-soft-delete`
- `hotfix/ACM-501-billing-api-timeout`

Always include the Linear ticket ID. It auto-links the branch to the issue.

### Commits
We use **Conventional Commits**:
```
feat: add retry logic to webhook delivery
fix: correct pagination cursor encoding
chore: upgrade fastapi to 0.110
docs: update API auth section
test: add unit tests for user deletion
```

Keep commits small and focused. One logical change per commit. Avoid "WIP" or "misc fixes" commits on PRs.

### Main branch rules
- `main` is protected — no direct pushes
- All changes go through PRs
- `main` auto-deploys to staging on merge
- Production deploys happen via release tags only (see Deployment)

---

## Pull Requests

### Before opening a PR
- Tests pass locally (`pytest`)
- Linting passes (`ruff check .`)
- Coverage hasn't dropped below 80%
- You've self-reviewed your diff
- Linear ticket linked in PR description

### PR template
Every PR auto-populates this template:
```
## What does this PR do?
Brief description of the change.

## Why?
Link to Linear ticket: ACM-XXX

## How to test?
Steps to verify the change works.

## Checklist
- [ ] Tests added/updated
- [ ] Docs updated if needed
- [ ] No secrets committed
```

### Review process
- Minimum **1 approval** required to merge
- Tag the relevant squad in `#code-review` if your PR is urgent
- Draft PRs are fine for early feedback — mark ready when done
- Review turnaround expectation: **same business day** for PRs under 200 lines, **24h** for larger ones

### Merge strategy
We use **squash and merge**. All commits in a branch get squashed into one commit on main. Write a clean, descriptive squash commit message — this is what shows up in the changelog.

---

## Deployment

### Staging
Automatic. Every merge to `main` triggers a GitHub Actions pipeline:
1. Run tests
2. Build Docker image
3. Push to ECR
4. Deploy to staging ECS cluster

Pipeline takes ~8 minutes. Monitor in the `#deployments` Slack channel or in GitHub Actions directly.

### Production
Production deploys are **manual and tag-based**.

```bash
git tag v2.4.1
git push origin v2.4.1
```

This triggers the production pipeline. Only engineers with `prod-deploy` permission can push tags. By default, you won't have this in your first month — that's intentional.

**Who can deploy to prod:** Senior engineers, tech leads, and on-call engineers. If you need something deployed urgently, ask in `#deployments`.

### Rollbacks
If a production deploy causes an incident:
```bash
# Redeploy the previous tag
git tag v2.4.1-rollback v2.4.0
git push origin v2.4.1-rollback
```

Or trigger a rollback directly in the AWS ECS console — ask **Marcus Webb** (DevOps) if you've never done this before.

---

## Testing Standards

### What we test
- **Unit tests** — all business logic functions, especially edge cases
- **Integration tests** — API endpoints (request in, response out)
- **No UI tests** — we don't maintain a Selenium/Playwright suite currently

### Coverage requirement
**80% minimum.** CI will fail if coverage drops below this. Check locally:
```bash
pytest --cov=app --cov-report=term-missing
```

### Test file conventions
- Unit tests: `tests/unit/test_<module>.py`
- Integration tests: `tests/integration/test_<endpoint>.py`
- Use `pytest` fixtures, not setUp/tearDown
- Mock external services — tests must pass without network access

---

## Code Review Culture

We review code, not people. Some norms:

- **Be specific.** "This could be cleaner" is not helpful. "Extract this into a helper function to keep the controller thin" is.
- **Distinguish blocking vs non-blocking.** Use `nit:` prefix for style suggestions that shouldn't block merge.
- **Approve when it's good enough**, not perfect. Perfect is the enemy of shipped.
- **Authors respond to every comment**, even if just to say "done" or "disagree — here's why."
- No passive-aggressive or dismissive comments. Code review is a teaching moment, not a power dynamic.

---

## On-Call

### Rotation
Every engineer joins the on-call rotation after their **3-month mark**. The schedule lives in PagerDuty and is published 4 weeks in advance in `#engineering`.

### Responsibilities
- Respond to PagerDuty alerts within 15 minutes during business hours, 30 minutes overnight
- Triage the issue — is it a real incident or a false alarm?
- Escalate to the relevant service owner if it's outside your expertise
- Write a brief incident note in `#incidents` for anything that caused user impact

### Runbook
Before your first on-call shift, read `docs/incident_runbook.md`. It covers how to use Datadog, how to diagnose common alerts, and who to escalate to for billing/infra/database issues.

### Compensation
Weekend on-call shifts earn 0.5 days comp time each. Log in Rippling under "On-Call Comp."

---

## Tools & Access

| Tool | Purpose | How to get access |
|---|---|---|
| GitHub | Code, PRs, CI | Invite sent on day 1, ask manager if missing |
| Linear | Issue tracking | Ask your manager |
| Slack | Communication | Invite sent to work email |
| Datadog | Logs, monitoring, APM | Ask **Marcus Webb** |
| 1Password | Credential management | IT sets up on day 1 |
| AWS Console | Infra (read-only for most) | Request in `#it-help` with justification |
| Figma | Design specs | Ask the design team in `#design` |
| Notion | Docs, meeting notes, RFCs | Auto-provisioned on Slack join |
| PagerDuty | On-call alerting | Added by DevOps at 3-month mark |
| Rippling | HR, payroll, time-off | Auto-provisioned, check your email |

**Database access:** Direct DB access (read or write) to staging requires a request in `#platform-team`. Production DB access is restricted to senior engineers and requires manager approval. Submit the request via the `#data-access` channel with your use case.

---

## Slack Channels — Must Join

| Channel | Purpose |
|---|---|
| `#engineering` | Company-wide engineering announcements |
| `#your-squad` | Your squad's day-to-day (ask manager for name) |
| `#deployments` | Staging and production deploy notifications |
| `#incidents` | Active incident tracking |
| `#code-review` | Request reviews for urgent PRs |
| `#dev-help` | Stuck on something? Ask here |
| `#platform-team` | API, infra, and access requests |
| `#it-help` | Laptop, software, account issues |
| `#random` | Off-topic, memes, life |

---

## Meetings

| Meeting | Cadence | Who |
|---|---|---|
| Squad standup | Daily, 9:30am | Your squad |
| Sprint planning | Bi-weekly Monday | Squad + PM |
| Sprint retro | Bi-weekly Friday | Squad |
| Engineering all-hands | Monthly | All engineering |
| 1:1 with manager | Weekly | You + your manager |
| Architecture review | Ad-hoc (RFC-triggered) | Senior engineers + leads |

Standups are async-first — post your update in the squad Slack channel if you can't attend. No one should be blocked waiting for the next standup.

---

## RFC Process

For significant technical decisions (new service, breaking API change, major architectural change), we write an RFC (Request for Comments).

1. Copy the RFC template from Notion (`Engineering > RFC Template`)
2. Fill in: problem, proposed solution, alternatives considered, trade-offs
3. Post in `#engineering` with a 5-business-day comment window
4. Address comments, update the doc
5. Tech lead signs off — then you can proceed

RFCs are not bureaucracy — they save you from building the wrong thing. If in doubt, write one.

---

## Key People

| Name | Role | Slack | Owns |
|---|---|---|---|
| Sarah Chen | Platform Lead | @sarah.chen | API architecture, platform services, billing access |
| Marcus Webb | DevOps / Infra | @marcus.webb | AWS, Datadog, CI/CD, database access |
| Priya Nair | Engineering Manager | @priya.nair | Team process, performance, escalations |
| David Kim | Tech Lead | @david.kim | Code standards, architecture reviews, RFC sign-off |
| Aaliya Torres | Senior Engineer | @aaliya.torres | Onboarding buddy coordinator, `#dev-help` champion |

---

## Engineering Principles

1. **Ship small, ship often.** Small PRs get reviewed faster and are easier to roll back.
2. **Make it work, then make it right.** Don't over-engineer on the first pass — refactor once the shape is clear.
3. **Leave the codebase better than you found it.** Boy Scout Rule — fix small things when you see them.
4. **Default to async.** Don't schedule a meeting when a Slack message or Linear comment will do.
5. **Incidents are blameless.** We fix systems, not people. Post-mortems focus on process gaps, not who made the mistake.
6. **Document the why, not just the what.** Code explains what it does. Comments explain why you made a non-obvious choice.
