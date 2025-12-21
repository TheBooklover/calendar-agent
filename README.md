# Calendar Agent
# AI Calendar Agent — V0 (OAuth + Infrastructure Foundation)

A deployed foundation for an AI-powered calendar planning agent.  
**V0 focuses on OAuth, API access, and real-world deployment constraints** (no AI logic included yet).

---

## What this is

This repository contains the first “production-shaped” version of a calendar agent:

- Google OAuth 2.0 (Authorization Code flow)
- Google Calendar API integration
- Deployed backend + browser-based frontend integration
- CORS-safe cross-origin calls (Replit → deployed API)
- Token persistence designed for a stateless host (no local file reliance)

This V0 exists to prove that the app can securely access a real calendar and operate reliably in a hosted environment.

---

## What this is not (yet)

V0 intentionally does **not** include AI/LLM planning logic.

That’s by design: an “AI calendar agent” only becomes meaningful once the foundations are solid:
- the auth is correct
- the data access is stable
- the deployments don’t break the user flow

---

## Product intent (V0)

Enable a user to:

1. Connect their Google account via OAuth
2. Grant the app calendar access (scoped)
3. Run a “Preview Plan” call that successfully uses Calendar API access

---

## Tech stack

### Frontend (V0)
- Replit-hosted static UI (HTML/CSS + JavaScript)
- Fetch-based API calls to a deployed backend

### Backend (V0)
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
5. Tokens are stored in an external store (Redis) so the backend remains stateless

---

## Key challenges & what I learned

### 1) OAuth redirect_uri mismatch (Error 400)
**Problem:** Google blocked sign-in with `redirect_uri_mismatch`.  
**Root cause:** OAuth client configuration mismatch (initially created the wrong client type and/or redirect URI didn’t match exactly).  
**Fix:** Switched to **Web Application OAuth** and configured an exact redirect URI:
- `https://<domain>/auth/callback`

**Learning:** OAuth failures are often configuration issues across systems—not code bugs.

---

### 2) Credential handling (credentials.json) and repo safety
**Problem:** OAuth credentials need to exist for the app to run, but must never be committed to git.  
**Fix:** Ensured secrets are excluded (`.gitignore`) and loaded via environment variables.

**Learning:** secure secret handling is part of product quality, not just engineering hygiene.

---

### 3) Token persistence on Render Free (ephemeral filesystem)
**Problem:** Render Free instances don’t guarantee filesystem persistence, so `token.json` disappears across restarts, breaking authenticated calls.  
**Fix:** Replaced file-based token storage with **external persistence (Upstash Redis)**.

**Learning:** stateless infrastructure requires external state storage. Designing for platform constraints is part of shipping.

---

### 4) Replit → Backend fetch issues (CORS + preflight)
**Problem:** Browser requests from Replit to the deployed API triggered cross-origin restrictions.  
**Fix:** Implemented/verified CORS configuration so `OPTIONS` preflight succeeds and `POST` requests work.

**Learning:** distributed systems often fail “between” components. Always validate network + browser behavior, not just backend logs.

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
- `OAUTH_TOKEN_KEY` (optional; default can be used)

### OAuth endpoints
- Start: `/auth/start`
- Callback: `/auth/callback`

---

## Roadmap (V1+)

Planned evolution after V0:

- Natural-language scheduling requests (“Move my 1:1 to next week”)
- Constraint-based planning (availability, preferences, working hours)
- Preference memory (e.g., “no meetings before 10am”)
- AI-generated plan preview with user approval
- Multi-user support (token storage keyed by user identity)
- Observability (logs/metrics) and safety guardrails

---

## Why this matters as an AI PM portfolio project

Most “AI agent” demos skip the hard parts (auth, hosting, state, constraints).  
This V0 demonstrates the part that makes AI products real: **building a trustworthy foundation** that can support intelligent behavior later.

---

## License
TBD

