# Resolve

Ticketing + RAG for publishing operations. Editorial, author and stylesheet queries are answered from the **latest revision** of each journal's files and from closed tickets, with citations. Work in progress: see the build status below.

## Status

| Area | State |
|---|---|
| Auth (Keycloak OIDC, PKCE), RBAC policy | done |
| Journals, articles, versioned documents, local file storage | done |
| Web UI: sign-in, journals, documents with version history, articles | done |
| Ingestion (PDF, DOCX, Markdown/text, EML), background worker, hybrid retrieval (pgvector + full-text, RRF) | done |
| Ask: LangGraph flow with citations, abstention, current-version-only answers; Ask tab; index status + retry | done |
| Tickets: raise (also from an unanswered Ask), assign, comment, resolve, lead approval; approved answers become citable knowledge, reopening withdraws them | done |
| Evaluation: seeded synthetic corpus, 168 golden questions, retrieval ablation, end-to-end scoring, thresholds (`eval/`) | done |
| Postgres row-level security on every tenant table (second line of defence behind the permission checks) | done |
| CI: lint, types, tests, licence gate, vulnerability scans, image build (`.github/workflows/ci.yml`) | done |
| MCP server with OAuth (Keycloak dynamic client registration + PKCE): 7 tools, a stylesheet resource, 2 prompts | done |
| Email intake, Langfuse, Docling adapter, eval thresholds in CI | not started |

## Run it locally

Requirements: Docker, Python 3.14 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
cp .env.example .env            # then change the secrets
docker compose up -d db keycloak litellm      # needs DEEPINFRA_API_KEY in .env
cd backend && uv sync && bash scripts/prestart.sh   # migrations + job-queue tables
uv run uvicorn app.main:app --port 8000     # API
uv run procrastinate --app=app.workers.queue.queue worker --queues ingestion   # indexing worker
uv run uvicorn app.mcp.server:app --port 8010   # MCP server (optional)
cd ../frontend && npm install && npm run dev  # UI on :5173
```

Models are chosen in `deploy/litellm.yaml` (DeepInfra: embeddings `BAAI/bge-m3`; chat `chat-fast` = Llama-4-Maverick by default, `chat-large` = Llama-3.3-70B as the quality option and fallback, `chat-small` = Llama-3.1-8B). Embeddings are 1024-dimensional; changing to a model with another size needs a migration and re-index.

Keycloak runs on <http://localhost:8081>. The realm in `deploy/keycloak/realm-export.json` seeds four dev users (admin, lead, assistant, viewer `@example.com`); their dev-only password is in that file.

## Deploy

`compose.prod.yml` runs the whole stack on one VPS behind Traefik with automatic HTTPS at `app.`, `auth.` and `mcp.` subdomains of your domain. Step-by-step setup, DNS, backups and updates: [deploy/PRODUCTION.md](deploy/PRODUCTION.md). The production Keycloak realm has no seeded users; the first administrator comes from `.env.prod`.

## MCP server

`app/mcp/server.py` exposes Resolve to MCP clients over streamable HTTP at `http://localhost:8010/mcp`. It authenticates with the same Keycloak realm as the web app: the server answers `401` with a pointer to its OAuth metadata, the client finds Keycloak, **registers itself** (dynamic client registration), the user logs in and consents, and the client sends a PKCE-issued token on every call. Tokens must carry the `resolve-api` audience, which the realm adds to every client by default.

| Tool | Reads or writes | What it does |
|---|---|---|
| `list_journals` | read | journals you belong to, with your role |
| `ask_resolve` | read | cited answer from current files and approved tickets; says so when it cannot answer |
| `search_knowledge` | read | the matching passages, no generated answer |
| `list_tickets`, `get_ticket` | read | browse tickets and read one |
| `suggest_answer` | read | drafts an answer to a ticket; nothing is saved |
| `create_ticket` | **write** | raises a ticket; without `confirm=true` it only returns a preview |

Also a `journal://{code}/stylesheet` resource (latest versions only) and two prompts (`triage_open_tickets`, `prepare_reply`).

Design points: an MCP session is **member-level only, never admin**, even for a web admin; row-level security is bound to the same identity. Unknown and not-permitted journals give the same "not found" message. Results quote documents and tickets, so each carries a notice that the text is data, not instructions. Unexpected errors are logged in full and reported generically. Every call logs tool, client, outcome and duration (`resolve.mcp`); there is no audit table yet.

Test it end to end with `python -m uv run python scripts/mcp_smoke.py` (from `backend/`; add `--print-url` to get the sign-in URL instead of opening a browser). It discovers Keycloak, registers itself, waits for you to sign in and consent, then calls every tool and checks the results (7 checks; `create_ticket` is only previewed). **Tested this way:** the FastMCP client, and the MCP Inspector up to the token step. **Known limit:** Claude Code refuses sign-in pages that are plain `http://`, so a real Claude Code or Claude Desktop session needs Keycloak and the MCP server behind `https` (not done). Connect with `claude mcp add --transport http resolve http://localhost:8010/mcp` and authenticate from `/mcp` once they are.

Dev Keycloak notes (`deploy/keycloak/realm-export.json`): client registration is open to anonymous callers, every registered client requires user consent, and the "sending host" check is relaxed because Docker rewrites the sender address (tighten it for production). Registered clients may only receive the `openid`, `profile`, `email` and `resolve-api` scopes, and the `offline_access` scope is removed from the realm: MCP clients ask for it whenever it is advertised, and tokens issued without `email` or the `resolve-api` audience are rejected. The MCP server tells clients which scopes to request. `github.com` is a trusted registration host so the MCP Inspector can register. Keycloak only imports the realm on first start; after changing the file, recreate its database (`DROP DATABASE keycloak; CREATE DATABASE keycloak;`) and restart it.

## Security model

Access is checked twice. The services apply the role matrix (`app/domain/policy.py`), and Postgres row-level security enforces journal isolation underneath it (migration `0004`, `app/core/rls.py`):

- Each API request opens one session. Before sign-in it is anonymous (sees no rows); after the token is verified it is bound to the user. Every transaction then runs `SET LOCAL ROLE resolve_app` with `app.user_id` / `app.is_admin` set, so a forgotten check or a query without a journal filter returns nothing instead of another journal's rows.
- Rows of other journals are invisible, so fetching one by id returns **404**, not 403: the response does not confirm it exists.
- The identity settings are transaction-local and cannot leak between requests on a pooled connection.
- The job worker, migrations and the eval harness connect without a context and are deliberately privileged. `app_user` is not row-protected (people are looked up by email when adding members).
- A new table must be added to the policies or to the allowlist in `tests/integration/test_rls.py`, or that test fails.

## How fast is Ask?

About 1-2 seconds typically, and the answer panel shows where the time went. Two things cut it further: the UI embeds your question while you are still typing, and repeated questions are answered from a cache that is invalidated whenever the journal's documents or approved tickets change. Most of the remaining time is the round trip to the model provider, which varies a lot with your network. Measurements and the model comparison are in [`eval/README.md`](eval/README.md).

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request: ruff and mypy, the full test suite (integration tests start pgvector containers and send every API request through RLS), frontend lint, typecheck and build, a licence gate (no GPL, AGPL or SSPL in shipped Python or npm packages; LGPL such as psycopg is allowed), `pip-audit` and `npm audit`, and a Docker image build. The eval harness runs offline in the test suite; the real-model eval and its thresholds (`eval/thresholds.json`) need an API key and are run by hand.

## Quality, measured

`eval/` scores retrieval and the real Ask flow on a synthetic corpus with stale-version, cross-journal, article-exception, unapproved-ticket and unanswerable traps. Latest run: **95.8%** of 168 questions passed end to end (default fast model; the 70B scores 97.0%), **0.0%** of answers mentioned a stale or another journal's value, retrieval recall@5 97.8%. Details, the ablation table and what the numbers changed are in [`eval/README.md`](eval/README.md) and [`eval/reports/latest.md`](eval/reports/latest.md). The corpus is synthetic, so treat absolute numbers as friendly.

## Tests and checks

```bash
cd backend
uv run pytest tests            # unit + integration (integration starts a pgvector container)
uv run mypy app tests && uv run ruff check app tests
cd ../frontend && npx tsc -p tsconfig.build.json
```

After changing API routes, regenerate the TypeScript client with `bash scripts/generate-client.sh`.

## Layout

```
backend/app/{api,core,domain,services,repositories,storage}   FastAPI app, layered
frontend/src                                                  React + TanStack Router/Query
deploy/keycloak/realm-export.json                             seeded identity realm
```

The architecture and roadmap live in the project plan; scaffolding came from the MIT-licensed `fastapi/full-stack-fastapi-template`.
