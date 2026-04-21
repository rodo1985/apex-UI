SHELL := /bin/zsh

PYTHON_DIR := backend
FRONTEND_DIR := frontend

.PHONY: help dev dev-api dev-web sync-strava test test-api test-web lint lint-api lint-web build build-web docker-note

help:
	@printf "\033[1;36m\n🏁 APEX Progress Portal\n\033[0m"
	@printf "\033[0;37mA small React + FastAPI portal for reviewing APEX progress data.\n\n\033[0m"
	@printf "\033[1;33m🚀 Run\n\033[0m"
	@printf "  \033[1mmake dev\033[0m           Start the frontend and backend in two terminals.\n"
	@printf "  \033[1mmake dev-api\033[0m       Run the FastAPI backend with uvicorn reload.\n"
	@printf "  \033[1mmake dev-web\033[0m       Run the Vite frontend.\n\n"
	@printf "  \033[1mmake sync-strava\033[0m   Run one manual Strava activity sync into Supabase.\n\n"
	@printf "\033[1;33m🧪 Test\n\033[0m"
	@printf "  \033[1mmake test\033[0m          Run backend and frontend tests.\n"
	@printf "  \033[1mmake test-api\033[0m      Run backend pytest suite.\n"
	@printf "  \033[1mmake test-web\033[0m      Run frontend Vitest suite.\n\n"
	@printf "\033[1;33m🧹 Lint\n\033[0m"
	@printf "  \033[1mmake lint\033[0m          Run backend Ruff and frontend ESLint.\n"
	@printf "  \033[1mmake lint-api\033[0m      Run backend Ruff.\n"
	@printf "  \033[1mmake lint-web\033[0m      Run frontend ESLint.\n\n"
	@printf "\033[1;33m📦 Build\n\033[0m"
	@printf "  \033[1mmake build\033[0m         Run the frontend production build.\n"
	@printf "  \033[1mmake build-web\033[0m     Build the Vite frontend only.\n\n"
	@printf "\033[1;33m🐳 Docker\n\033[0m"
	@printf "  \033[1mmake docker-note\033[0m   Explain the current non-Docker local workflow.\n\n"
	@printf "\033[1;33m📝 Notes\n\033[0m"
	@printf "  - Backend setup expects \033[1mcd $(PYTHON_DIR) && uv venv && uv sync\033[0m first.\n"
	@printf "  - Frontend setup expects \033[1mcd $(FRONTEND_DIR) && npm install\033[0m first.\n"
	@printf "  - Strava sync expects \033[1mSTRAVA_CLIENT_ID\033[0m, \033[1mSTRAVA_CLIENT_SECRET\033[0m, and a bootstrap \033[1mSTRAVA_REFRESH_TOKEN\033[0m.\n"
	@printf "  - Production deploy target: \033[1mnpx vercel --prod\033[0m from the repo root.\n\n"

dev:
	@printf "\033[1;31mOpen two terminals and run:\n\033[0m"
	@printf "  1. \033[1mmake dev-api\033[0m\n"
	@printf "  2. \033[1mmake dev-web\033[0m\n"

dev-api:
	cd $(PYTHON_DIR) && uv run uvicorn apex_portal_api.main:app --reload

dev-web:
	cd $(FRONTEND_DIR) && npm run dev

sync-strava:
	cd $(PYTHON_DIR) && uv run python -m apex_portal_api.strava_sync

test: test-api test-web

test-api:
	cd $(PYTHON_DIR) && uv run pytest

test-web:
	cd $(FRONTEND_DIR) && npm run test

lint: lint-api lint-web

lint-api:
	cd $(PYTHON_DIR) && uv run ruff check .

lint-web:
	cd $(FRONTEND_DIR) && npm run lint

build: build-web

build-web:
	cd $(FRONTEND_DIR) && npm run build

docker-note:
	@printf "\033[1;35mNo local Docker workflow is required right now.\n\033[0m"
	@printf "This portal reads a remote Supabase/Postgres database and is meant to stay simple.\n"
	@printf "Use \033[1muv\033[0m for the backend and \033[1mnpm\033[0m for the frontend during development.\n"
