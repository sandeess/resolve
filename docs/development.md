# Development

## Run it locally

Requirements: Docker, Python 3.14 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
cp .env.example .env            # then change the secrets; add DEEPINFRA_API_KEY
docker compose up -d db keycloak litellm
cd backend && uv sync && bash scripts/prestart.sh        # migrations + job-queue tables
uv run uvicorn app.main:app --port 8000                  # API
uv run procrastinate --app=app.workers.queue.queue worker --queues ingestion   # indexing worker
uv run uvicorn app.mcp.server:app --port 8010            # MCP server (optional)
cd ../frontend && npm install && npm run dev             # UI on http://localhost:5173
```

Or run the whole stack in containers, with the web app built into the backend image:

```bash
docker compose up -d --build        # UI + API on http://localhost:8000, MCP on :8010
```

Keycloak runs on <http://localhost:8081>. The realm in `deploy/keycloak/realm-export.json` seeds four development users (`admin@`, `lead@`, `assistant@`, `viewer@example.com`); their dev-only password is in that file. Never use that realm in production: `deploy/keycloak/make_prod_realm.py` derives the production one.

Models are chosen in `deploy/litellm.yaml`. Embeddings are 1024-dimensional (`BAAI/bge-m3`); another size needs a migration and a re-index.

## Keyboard shortcuts

`Ctrl/Cmd + K` opens the command palette (ask a question, jump to a journal, ticket or page, switch theme). `/` focuses the search box from anywhere.

## Tests and checks

```bash
cd backend
uv run pytest tests                            # unit + integration (integration starts pgvector containers)
uv run ruff check app tests && uv run mypy app tests
cd ../frontend
npx tsc -p tsconfig.build.json && npx biome check ./
python ../scripts/check_npm_licenses.py        # licence gate for shipped npm packages
```

After changing API routes, regenerate the TypeScript client with `bash scripts/generate-client.sh`.

Evaluation (needs LiteLLM up and an API key): see [`eval/README.md`](../eval/README.md).

## Test the MCP server

```bash
cd backend
uv run python scripts/mcp_smoke.py              # opens your browser for sign-in
uv run python scripts/mcp_smoke.py --print-url  # prints the sign-in URL instead
```

It discovers Keycloak, registers itself, waits for you to sign in as a journal **member** (try `lead@example.com`; over MCP even an administrator only sees journals they belong to) and consent, then calls every tool. `create_ticket` is only previewed, so nothing is written.

Claude Code refuses sign-in pages that are plain `http://`, so connecting a real Claude Code session needs Keycloak and the MCP server on `https` (see [deployment](../deploy/PRODUCTION.md)).

## Layout

```
backend/app/{api,core,domain,services,repositories,storage,ingestion,rag,llm,mcp,workers}
frontend/src                          React + TanStack Router/Query, shadcn/ui, Tailwind
deploy/                               Keycloak realm + theme, LiteLLM config, production runbook
eval/                                 synthetic corpus, golden questions, scoring, reports
docs/                                 engineering and privacy documents
compose.yml, compose.prod.yml         development and production stacks
```

## Dev notes

- Keycloak imports its realm only on first start. After editing the realm file, recreate Keycloak's database (`DROP DATABASE keycloak; CREATE DATABASE keycloak;`) and restart it, or change the live realm in its admin console.
- Row-level security: a new tenant table must be added to the policies or to the allowlist in `tests/integration/test_rls.py`.
- `localhost` can add about 200 ms per request on Windows (IPv6 is tried first). When running the Vite dev server there, set `VITE_API_URL=http://127.0.0.1:8000` in `frontend/.env`.
