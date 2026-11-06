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

## 4b. Optional: your personal page at the bare domain

`deploy/site/index.html` is a small about-me page with Resolve as its first product. It is served at `https://<domain>` and `https://www.<domain>` by a tiny nginx container, and it is **off by default** so it never replaces a site you already have.

To turn it on: point the apex (`@`) and `www` A records at this server (DNS only), set `COMPOSE_PROFILES=site` in `.env.prod` (the bootstrap script asks), and run `docker compose --env-file .env.prod -f compose.prod.yml up -d`. Edit the text in `deploy/site/index.html` any time; it is plain HTML, no build step.

The page ships its own search and AI-agent metadata: title and description, canonical URL, Open Graph and Twitter cards (`og.png`), schema.org JSON-LD (Person, WebSite, ProfilePage, SoftwareApplication), `robots.txt`, `sitemap.xml` and a plain-text `llms.txt` for AI agents. After the DNS switch: submit `https://<domain>/sitemap.xml` in Google Search Console, and check the link preview by pasting the URL into a chat or a social post. If you change the text, keep `llms.txt` and the JSON-LD in `index.html` in step with it.

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

* **Update:** `cd /opt/resolve && sudo bash deploy/update.sh` pulls the latest code, rebuilds, restarts and prints the health. Migrations run automatically (`prestart`) and are safe to re-run.
* **Backups:** `sudo bash deploy/backup.sh` writes the app database, Keycloak's database (your users) and the uploaded files to `/var/backups/resolve`, checks that the dumps are not empty, and removes copies older than 14 days. Run it nightly:
  ```bash
  echo '17 3 * * * root cd /opt/resolve && bash deploy/backup.sh >> /var/log/resolve-backup.log 2>&1' | sudo tee /etc/cron.d/resolve-backup
  ```
  A backup on the same disk does not survive losing the server: also copy `/var/backups/resolve` somewhere else (your PC with `scp`, or object storage). The script was tested by restoring a dump into a scratch database.
* **Restore** (replace `DATE` with the file's date; this overwrites current data):
  ```bash
  cd /opt/resolve
  C="docker compose --env-file .env.prod -f compose.prod.yml"
  $C stop backend worker mcp keycloak
  $C exec -T db psql -U postgres -c "drop database app" -c "create database app"
  $C exec -T db psql -U postgres -c "drop database keycloak" -c "create database keycloak"
  zcat /var/backups/resolve/app-DATE.sql.gz      | $C exec -T db psql -U postgres -d app
  zcat /var/backups/resolve/keycloak-DATE.sql.gz | $C exec -T db psql -U postgres -d keycloak
  docker run --rm -v resolve_app-files:/data -v /var/backups/resolve:/in alpine sh -c "rm -rf /data/* && tar xzf /in/files-DATE.tgz -C /data"
  $C up -d
  ```
  Practise it once on a spare copy before you need it.
* **Rotate secrets:** edit `.env.prod`, then `up -d` again. Changing `POSTGRES_PASSWORD` also needs `ALTER USER postgres PASSWORD '...'` in the running database.
* **Logs:** `docker compose --env-file .env.prod -f compose.prod.yml logs -f backend worker mcp`.

## Things to know

* The realm import runs only on the very first start. Later changes to `realm-prod.json` are ignored; make them in the Keycloak console or recreate the Keycloak database.
* MCP clients register themselves with Keycloak; only `localhost`, `127.0.0.1` and `claude.ai` are trusted for that (the MCP Inspector, which identifies itself as `github.com`, is not).
* Resolve calls the LLM through DeepInfra. Your document text leaves the server for that provider; check that this fits your data policy.
* Single server, no high availability. Uploads and the database live in Docker volumes on that machine.
