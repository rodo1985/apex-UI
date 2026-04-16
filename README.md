# APEX Progress Portal

APEX Progress Portal is a small read-only web app for reviewing endurance
training and nutrition progress online. It combines a React frontend with a
FastAPI backend that reads the same Supabase/Postgres data already used by the
`apex-mcp-server` project.

The goal is to keep the experience simple: open the portal, review the latest
tracked day, inspect profile context and reusable foods, review past logs, and
track how fuelling and training are evolving over time.

## Key Features / Scope

- Opens on the latest tracked day by default, so the portal is useful even
  when today has no new logs yet.
- Shows one athlete's selected-day dashboard with:
  - food vs target calories
  - macro progress
  - stacked meals and activities for easier phone review
  - expandable meal ingredient detail
- Shows a dedicated profile view with body metrics and stored APEX profile
  documents.
- Shows a dedicated food product table for reusable foods already stored in the
  MCP database.
- Shows past tracked days with quick review metrics and counts.
- Shows evolution trends for food, exercise, macros, activity load, and
  logging consistency.
- Adds a mobile sidebar drawer with a hamburger toggle for easier navigation on
  smaller screens.
- Reuses the APEX visual language: dark workspace, teal brand accent, and APEX
  logo/wordmark.
- Deploys as one Vercel project with:
  - `frontend/` at `/`
  - `backend/` at `/api`
- Reads directly from the MCP wellness tables:
  `user_profiles`, `food_products`, `daily_targets`, `daily_meals`,
  `meal_items`, and `activity_entries`.

### Out Of Scope

- Writing or editing meals, targets, or activities
- Multi-user account management
- Full MCP/OAuth login inside the portal
- Rebuilding the original APEX coaching workspace

## Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for backend environments and dependency
  management
- Node.js current LTS with `npm`

### Backend setup with `uv`

```bash
cd backend
uv venv
uv sync
cp .env.example .env.local
```

The backend reads environment variables from `backend/.env.local` by default.

### Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

## How To Run

### Run the backend

```bash
cd backend
uv run uvicorn apex_portal_api.main:app --reload
```

The local API is available at `http://127.0.0.1:8000`.

### Run the frontend

```bash
cd frontend
npm run dev
```

The local portal is available at `http://127.0.0.1:5173`. In local
development, Vite proxies `/api/*` requests to the FastAPI server.

### Useful repo commands

```bash
make help
make dev
make test
make lint
make build
```

## Configuration

### Backend environment variables

Copy [backend/.env.example](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/backend/.env.example)
to `backend/.env.local`.

Required:

- `DATABASE_URL` or `APEX_DATABASE_URL`
  Postgres connection string for the `apex-mcp-server` database. The simplest
  local default matches that repo's Docker setup:
  `postgresql://apex:apex@127.0.0.1:54329/apex_mcp_server`.
- `APEX_PORTAL_SUBJECT`
  The MCP/Supabase subject whose progress should be shown in the portal.

Recommended:

- `APEX_PORTAL_ACCESS_TOKEN`
  Optional simple access token required by the API and unlock screen. This is
  the recommended production privacy guard for the single-athlete portal.
- `APEX_ALLOWED_ORIGINS`
  Comma-separated local/dev origins for CORS.
- `APEX_PORTAL_TIMEZONE`
  Used to resolve the default “today” date on the backend.
- `APEX_PORTAL_ATHLETE_NAME`
  Optional display-name override for the profile and sidebar.

### Frontend environment variables

Copy [frontend/.env.example](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/frontend/.env.example)
to `frontend/.env.local`.

- `VITE_API_BASE_URL`
  Optional API base override. Defaults to `/api`.

## Project Structure

- [backend](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/backend)
  FastAPI service, Supabase/Postgres read queries, and backend tests.
- [frontend](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/frontend)
  Vite React portal, APEX-inspired UI, and frontend tests.
- [docs/APEX_PORTAL_IMPLEMENTATION.md](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/docs/APEX_PORTAL_IMPLEMENTATION.md)
  Human-readable implementation guide for the portal architecture and workflow.
- [vercel.json](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/vercel.json)
  Root Vercel Services configuration for the frontend and backend.
- [Makefile](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/Makefile)
  Guided development commands for local work.

## Vercel Deployment

This repo is configured for a single Vercel project using Services:

- `frontend/` serves the React portal at `/`
- `backend/index.py` serves the FastAPI API at `/api`

Suggested deployment flow:

```bash
cd frontend
npm install

cd ../backend
uv sync

cd ..
npx vercel link
npx vercel env add DATABASE_URL
npx vercel env add APEX_PORTAL_SUBJECT
npx vercel env add APEX_PORTAL_ACCESS_TOKEN
npx vercel --prod
```

If your Vercel project is already linked, `npx vercel --prod` from the repo
root is enough.

## Contributing / Development Notes

- Keep the backend read-only unless a current product need requires writes.
- Keep the portal queries aligned with the `apex-mcp-server` tables and daily
  summary semantics.
- Update this README and
  [docs/APEX_PORTAL_IMPLEMENTATION.md](/Users/REDONSX1/.codex/worktrees/410e/apex-UI/docs/APEX_PORTAL_IMPLEMENTATION.md)
  whenever setup, API behavior, or deployment changes.
