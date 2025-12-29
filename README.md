# AI Calendar Agent

A production-shaped calendar agent built in deliberate stages, moving from infrastructure → planning intelligence → AI.

This repository documents that progression explicitly, with each version solving a distinct product problem.

---

## V0.4 – OAuth & Infrastructure Foundation

### Summary
V0.4 establishes a secure, deployable foundation for an AI-powered calendar agent.  
This version focuses entirely on **OAuth, API access, and real-world deployment constraints**. No planning or AI logic is included yet.

---

## What this is

This repository contains a production-shaped backend for a calendar agent, including:

- Google OAuth 2.0 (Authorization Code flow)
- Google Calendar API integration
- Deployed backend + browser-based frontend integration
- CORS-safe cross-origin calls (Replit → deployed API)
- Token persistence designed for stateless hosting (no local file reliance)

This version exists to prove the app can securely access a real calendar and operate reliably in a hosted environment.

---

## What this is not (yet)

V0.4 intentionally does **not** include AI or scheduling intelligence.

That is by design. An “AI calendar agent” only becomes meaningful once:
- authentication is correct
- calendar access is reliable
- deployments don’t break user flows

---

## Product intent (V0.4)

Enable a user to:

1. Connect their Google account via OAuth
2. Grant scoped calendar access
3. Successfully make authenticated Calendar API calls via a deployed backend

---

## Tech stack

### Frontend
- Replit-hosted static UI (HTML/CSS + JavaScript)
- Fetch-based API calls to a deployed backend

### Backend
- **Python**
- **FastAPI** (REST API)
- **Uvicorn** (ASGI server)

### External services / APIs
- **Google OAuth 2.0**
- **Google Calendar API**
- **Render** (backend hosting)
- **Cloudflare** (domain + HTTPS)
- **Upstash Redis** (token persistence for stateless hosting)

---

## High-level architecture

Frontend (Replit)  
→ calls Backend (FastAPI on Render, via custom domain)  
→ uses Google Calendar API

OAuth flow:
1. Frontend triggers `/auth/start`
2. Backend redirects to Google consent screen
3. Google redirects back to `/auth/callback`
4. Backend exchanges code for tokens
5. Tokens are stored externally (Redis) so the backend remains stateless

---

## Key challenges & what I learned (V0.4)

### 1) OAuth redirect_uri mismatch (Error 400)
**Problem:** Google blocked sign-in with `redirect_uri_mismatch`.  
**Root cause:** OAuth client configuration mismatch (wrong client type and/or incorrect redirect URI).  
**Fix:** Switched to **Web Application OAuth** and configured an exact redirect URI:
- `https://<domain>/auth/callback`

**Learning:** OAuth failures are often configuration issues across systems, not code bugs.

---

### 2) Credential handling and repo safety
**Problem:** OAuth credentials are required at runtime but must never be committed.  
**Fix:** Ensured secrets are excluded (`.gitignore`) and injected via environment variables.

**Learning:** Secure secret handling is part of product quality, not just engineering hygiene.

---

### 3) Token persistence on Render Free (ephemeral filesystem)
**Problem:** Render Free instances don’t guarantee filesystem persistence, causing `token.json` to disappear across restarts.  
**Fix:** Replaced file-based token storage with **external persistence using Upstash Redis**.

**Learning:** Stateless infrastructure requires external state storage. Designing for platform constraints is part of shipping.

---

### 4) Replit → Backend fetch issues (CORS + preflight)
**Problem:** Browser requests triggered cross-origin restrictions.  
**Fix:** Implemented and verified proper CORS configuration so `OPTIONS` preflight and `POST` requests succeed.

**Learning:** Distributed systems often fail *between* components. Always validate browser and network behavior, not just backend logs.

---

---

## V0.5 – Slot-Aware Planning (Deterministic Baseline)

### Summary
V0.5 introduces a **deterministic, non-AI planning engine** that produces human-reasonable schedules.

This version defines what “good scheduling” means *before* introducing AI, creating a clear, testable baseline for future intelligence.

---

## Key challenges, solutions, and learnings (V0.5)

### 1) Naive greedy scheduling wasted usable time
**Challenge:**  
The initial planner could only schedule one goal per free slot, leaving usable time unused.

**Solution:**  
Reworked the planner to be **slot-aware**, allowing multiple goal blocks to be packed into a single free interval while preserving deterministic behavior and priority order.

**Learning:**  
Correct logic isn’t enough. Product systems must align with how users expect time to be used.

---

### 2) Minimum block sizes are a product decision
**Challenge:**  
Without constraints, the planner produced unrealistic micro-blocks (e.g. 5–10 minutes of “Deep Work”).

**Solution:**  
Introduced **per-goal minimum block sizes**, with sensible defaults and configurable overrides.

**Learning:**  
Constraints encode product values and should be explicit, not implicit edge cases.

---

### 3) Buffer placement strongly affects UX
**Challenge:**  
Applying buffers after every block wasted time and prevented valid schedules from forming.

**Solution:**  
Changed buffer semantics so buffers are applied **between blocks**, not after the final block in a slot.

**Learning:**  
Small timing rules can have outsized impact on perceived quality.

---

### 4) Partial allocation enables better schedules
**Challenge:**  
A strict greedy approach fully allocated the first goal, even when that blocked subsequent goals.

**Solution:**  
Implemented **partial allocation** to intentionally reserve room for the next prioritized goal, resulting in more balanced schedules.

**Learning:**  
Better outcomes often come from not maximizing the first choice — a key insight for future AI planning.

---

### 5) Tests as proof of product behavior
**Challenge:**  
Without tests, it was difficult to prove determinism or demonstrate improvement.

**Solution:**  
Added:
- A positive acceptance test demonstrating improved slot packing
- A negative control test proving behavior changes when constraints change

**Learning:**  
Tests can document product intent, not just correctness. These tests now serve as a baseline for AI-driven planning.

---

## Why V0.5 matters

V0.5 establishes a fully explainable, deterministic scheduling baseline that:
- Produces human-reasonable schedules
- Makes assumptions explicit
- Is predictable, testable, and debuggable
- Serves as a control group for future AI planners

This version intentionally contains **no AI**.

---

## How to run (developer notes)

> These steps are intentionally minimal. This repo is designed to be a portfolio artifact as much as a codebase.

### Environment variables (backend)

Required:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `OAUTH_REDIRECT_URI`

Token persistence (Upstash):
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `OAUTH_TOKEN_KEY` (optional)

### OAuth endpoints
- Start: `/auth/start`
- Callback: `/auth/callback`

---

## Roadmap (V1+)

Planned evolution after V0.5:

- Natural-language scheduling requests
- Constraint-based planning (availability, preferences, working hours)
- Preference memory (e.g. “no meetings before 10am”)
- AI-generated plan previews with user approval
- Multi-user support
- Observability and safety guardrails

---

## Why this matters as an AI PM portfolio project

Most “AI agent” demos skip the hard parts.  
This project demonstrates **deliberate product progression**:

- Infrastructure first (V0.4)
- Explainable planning logic (V0.5)
- AI introduced only after a solid baseline exists

This mirrors how real AI products are built in production.

---

## License
TBD
