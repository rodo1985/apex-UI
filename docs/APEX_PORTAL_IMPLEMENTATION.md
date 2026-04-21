# APEX Progress Portal Implementation

## Purpose

APEX Progress Portal is a read-only companion web app for the existing APEX
MCP wellness backend. It gives the athlete a simple place to review:

- the current day
- recent logged days
- longer-term trends in fuelling and training

This repo intentionally does not recreate the full product workspace. The goal
is a focused review surface that is easy to deploy, easy to understand, and
easy to maintain.

## Product Context

The existing APEX ecosystem already stores persistent wellness data in the
Postgres schema behind `apex-mcp-server`. The portal reads those MCP wellness
records directly so the review experience matches the same data the MCP tools
already expose.

For this portal, only the read side matters. The athlete should be able to open
one website and quickly answer questions such as:

- How is today going against the target?
- What did I eat and what training did I do?
- What profile context and goals are currently stored?
- Which reusable food products already exist in the catalog?
- Which previous days are worth reviewing?
- Is my fuelling and training trend moving in the right direction?

## What Is Deployed

- A React frontend served from `frontend/`
- A FastAPI backend served from `backend/index.py`
- A single Vercel project using Services routing
- A Supabase/Postgres connection string passed by environment variable

## High-Level Workflow

```mermaid
flowchart LR
    User["Athlete opens portal"] --> Web["React frontend"]
    Web --> API["FastAPI read API"]
    API --> DB["Supabase / Postgres"]
    DB --> API
    API --> Web
    Web --> Views["Today, Profile, Food products, History, Trends"]
```

## Main Components

### Frontend

- `frontend/src/App.tsx`
  Main portal state, section switching, loading, and unlock handling.
- `frontend/src/components/MarkdownContent.tsx`
  Lightweight markdown renderer for profile sections.
- `frontend/src/components/Brand.tsx`
  APEX icon and wordmark components reused across the portal.
- `frontend/src/components/PortalShell.tsx`
  Collapsible desktop rail, mobile drawer, and shared content shell.
- `frontend/src/components/TrendChart.tsx`
  Interactive multi-series SVG chart with point tooltips for achieved versus
  target trend views.
- `frontend/src/lib/api.ts`
  Small fetch client for the backend endpoints, including the product catalog
  and per-product usage trend reads.

### Backend

- `backend/src/apex_portal_api/main.py`
  FastAPI app assembly and route definitions.
- `backend/src/apex_portal_api/config.py`
  Environment-driven runtime settings.
- `backend/src/apex_portal_api/store.py`
  Supabase/Postgres read queries aligned to the MCP wellness tables.
- `backend/src/apex_portal_api/models.py`
  Typed API response models used by the routes.

## Data Inputs

The backend reads from these existing tables:

- `public.user_profiles`
- Either the legacy review schema:
  `public.food_products`, `public.daily_targets`, `public.daily_meals`,
  `public.meal_items`, `public.activity_entries`
- Or the newer normalized schema:
  `public.food_items`, `public.daily_nutrition_targets`,
  `public.meal_logs`, `public.meal_ingredients`, `public.activities`

The portal does not write to those tables. It only aggregates and presents the
data already stored by the MCP workflows.

Product usage analytics are derived from the linked meal fact tables:

- legacy: `daily_meals` + `meal_items.product_id`
- normalized: `meal_logs` + `meal_ingredients.food_id`

That keeps favorites and trends aligned with meal edits and deletes without
introducing a mutable product counter.

## Important Design Decisions

### Automatic schema detection

The portal still reads one configured `APEX_PORTAL_SUBJECT`, because that is
what the upstream MCP layer uses for profile data and for the legacy wellness
tables. When the connected database uses the newer normalized schema, the
backend resolves the matching app-level `user_id` before it runs the daily
summary queries.

This keeps local development flexible:

- the current production deployment can keep using the legacy subject-based
  wellness tables
- newer Supabase projects can use the normalized `user_id`-based tables
- the same backend code detects the available schema at runtime

### Latest tracked day default

The portal opens on the latest tracked day instead of blindly opening the
current calendar day. This matters because a read-only review portal is much
more helpful when it lands on the most recent real data instead of an empty
screen on rest days or before the first log of the day.

### Optional portal access token

An optional `APEX_PORTAL_ACCESS_TOKEN` lets the deployed site stay private
without introducing a larger auth workflow. If the token is configured, the
frontend shows a minimal unlock screen and the backend expects a bearer token.

For local development, the Vite app can also read `VITE_PORTAL_ACCESS_TOKEN`
from `frontend/.env.local`. That keeps the browser requests authenticated
without manually unlocking the portal after every fresh session or restart.

### Read-only API surface

The backend only exposes the reporting views the portal needs:

- portal bootstrap/context
- one day snapshot
- history summaries
- trend series

That keeps the backend small and lowers the risk of drifting away from the
authoritative MCP data model.

The current read-only routes are:

- `/portal/bootstrap`
- `/portal/day`
- `/portal/products`
- `/portal/product-usage/trends`
- `/portal/history`
- `/portal/trends`

### Derived product usage analytics

The product catalog now includes additive usage summaries computed from linked
meal rows. Each product response includes:

- trailing-window linked uses
- lifetime linked uses
- last-used date

The trailing window is controlled by `date_to` and `window_days` on
`/portal/products`, while `/portal/product-usage/trends` exposes an oldest-first
daily series for one product. The implementation details and rollout notes live
in [PRODUCT_CONSUMPTION_ANALYTICS.md](PRODUCT_CONSUMPTION_ANALYTICS.md).

## Outputs

The user-facing outputs are:

- a today snapshot with stacked meal and activity detail
- a profile page with metrics and stored markdown documents in open-layout
  sections
- a reusable food product table with search, sort, recent-use, lifetime-use,
  and last-used data
- a history list with current-versus-target nutrition chips for each logged day
- a trends view showing longer-term evolution plus target overlays for food and
  macro metrics

## Dependencies

- Backend: `uv`, FastAPI, asyncpg, pydantic-settings
- Frontend: React, Vite, Vitest
- Deployment: Vercel Services
- Data source: Supabase/Postgres

## Review Notes

When reviewing future changes, the most important question is whether the
portal still matches the `apex-mcp-server` storage semantics. If the MCP
server changes how it stores targets, meals, or activities, the portal queries
and README should be updated at the same time.
