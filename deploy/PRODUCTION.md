# Deploying Resolve on a VPS

Result: HTTPS on three subdomains of your domain (`sortitouthq.com` below), one small server.

| Address | What |
|---|---|
| `https://app.sortitouthq.com` | web app and API |
| `https://auth.sortitouthq.com` | Keycloak sign-in |
| `https://mcp.sortitouthq.com` | MCP server (Claude Code / Claude Desktop) |

Only ports 80 and 443 are published. Traefik gets and renews Let's Encrypt certificates by itself. Keycloak's admin console and the `master` realm are reachable only from the server itself.

## Fastest path: any Ubuntu VPS, one script

Any VPS with 2 vCPU / 4 GB or more works (a 2 vCPU / 8 GB / 100 GB plan around 1,300 INR a month leaves plenty of room). Point the three DNS records at the server (section 2), then on the server:

```bash
git clone https://github.com/sandeess/resolve.git /opt/resolve
cd /opt/resolve && sudo bash deploy/bootstrap-vps.sh
```

The script asks for your domain, email and DeepInfra key, installs Docker, a firewall and swap, generates every secret into `.env.prod` (root-only), builds the production realm and starts the stack. The sections below explain each step if you prefer to do it by hand.

## 1. Server

**On Google Cloud** (what `deploy/gcp/create-vm.sh` automates): install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), run `gcloud auth login`, make sure the project has billing enabled, then

```bash
PROJECT=your-project-id bash deploy/gcp/create-vm.sh
```

It reserves a static IP, opens ports 80 and 443, and creates an `e2-medium` Ubuntu 24.04 VM (2 vCPU, 4 GB) with Docker and swap. Expect roughly 25 USD a month for the VM plus a few dollars for disk and IP; new Google Cloud accounts usually have trial credit (check the current offer). Cloud Run is not a fit: Keycloak, Postgres and the worker need a long-running machine with a disk. The script prints the IP for the DNS step.

**Anywhere else:** any Linux VPS with 2 vCPU / 4 GB RAM and 20 GB disk is enough (e.g. Hetzner CX22, or Oracle Cloud's Always Free ARM instance). Ubuntu 24.04:

```bash
curl -fsSL https://get.docker.com | sh
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
```

## 2. DNS (Cloudflare)

Add three **A records** pointing at the server's IPv4 address: `app`, `auth`, `mcp`. Set each to **DNS only** (grey cloud) so Let's Encrypt can reach the server on port 80. Leave your existing `sortitouthq.com` records alone.

## 3. Get the code and configure

```bash
git clone https://github.com/<you>/resolve.git && cd resolve
cp .env.prod.example .env.prod      # fill in every value; generate secrets with openssl
python3 deploy/keycloak/make_prod_realm.py --domain sortitouthq.com
```

`RESOLVE_ADMIN_EMAIL` / `RESOLVE_ADMIN_INITIAL_PASSWORD` create the first administrator. The password is temporary: Keycloak makes you choose a new one on first sign-in.

## 4. Start

```bash
docker compose --env-file .env.prod -f compose.prod.yml up -d --build
docker compose --env-file .env.prod -f compose.prod.yml ps
```

The first start builds the image (a few minutes) and Keycloak imports the realm. Open `https://app.sortitouthq.com` and sign in.

## 5. Let people ask for access (Google Form)

The public front page has a **Request access** button that opens a Google Form inside the page, so new people reach you without an account.

1. In Google Forms create a form. Suggested questions: full name, work email, organisation, which journal(s), role (author / editor / copyeditor / production / other), and why they need access.
2. Turn on email notifications for new responses (Responses tab, three dots, "Get email notifications for new responses") so each request lands in your inbox.
3. Copy the form's link (Send, link icon) and put it in `.env.prod` as `ACCESS_REQUEST_URL`, then rebuild: `docker compose --env-file .env.prod -f compose.prod.yml up -d --build` (the value is baked into the web app at build time).

When a request arrives: create their account in Keycloak (below), then add their email to the journal on the **People** page. They get access the first time they sign in.

## 6. Add people and journals

Sign in as the administrator and create a journal. To add users, use the Keycloak admin console through an SSH tunnel (it is not public):

```bash
ssh -L 8081:localhost:8080 you@server   # then open http://localhost:8081/admin
```

Alternatively `docker compose ... exec keycloak` into the container. Make a user in realm **resolve**, then add them to a journal in the app. Give someone the `resolve-admin` realm role only if they should administer everything.

## 7. Connect Claude Code

```bash
claude mcp add --transport http resolve https://mcp.sortitouthq.com/mcp
```

Then `/mcp` → **resolve** → **Authenticate**. Sign in as a user who belongs to a journal (over MCP even an administrator only sees journals they are a member of).

## Operations

* **Update:** `git pull && docker compose --env-file .env.prod -f compose.prod.yml up -d --build`. Migrations run automatically (`prestart`).
* **Backups:** nightly database dump and a copy of the uploads volume, kept off the server:
  ```bash
  docker compose --env-file .env.prod -f compose.prod.yml exec -T db pg_dump -U postgres app | gzip > app-$(date +%F).sql.gz
  docker compose --env-file .env.prod -f compose.prod.yml exec -T db pg_dump -U postgres keycloak | gzip > keycloak-$(date +%F).sql.gz
  docker run --rm -v resolve_app-files:/data -v "$PWD":/out alpine tar czf /out/files-$(date +%F).tgz -C /data .
  ```
  Restore by piping a dump into `psql` on a fresh database, then restoring the files volume. Try a restore once before you need it.
* **Rotate secrets:** edit `.env.prod`, then `up -d` again. Changing `POSTGRES_PASSWORD` also needs `ALTER USER postgres PASSWORD '...'` in the running database.
* **Logs:** `docker compose --env-file .env.prod -f compose.prod.yml logs -f backend worker mcp`.

## Things to know

* The realm import runs only on the very first start. Later changes to `realm-prod.json` are ignored; make them in the Keycloak console or recreate the Keycloak database.
* MCP clients register themselves with Keycloak; only `localhost`, `127.0.0.1` and `claude.ai` are trusted for that (the MCP Inspector, which identifies itself as `github.com`, is not).
* Resolve calls the LLM through DeepInfra. Your document text leaves the server for that provider; check that this fits your data policy.
* Single server, no high availability. Uploads and the database live in Docker volumes on that machine.
