# Privacy, data flow and zero data retention (ZDR)

Publishers handle unpublished manuscripts, reviewer reports and author correspondence. This page says exactly where that data goes, what Resolve keeps, what the model provider's published policy says, and how to tighten it further. It is written to be handed to a security or legal reviewer.

## Principles

1. **Your documents stay on your server.** Files, text, vectors and tickets live in your own Postgres and storage volume.
2. **The model sees only what a question needs.** Per question: the question plus the handful of retrieved passages the asker is allowed to see. Not the whole library, not other journals.
3. **No content in logs.** The application logs identifiers, tool names, outcomes and durations, never question or answer text (see the table below).
4. **The model provider is swappable.** The app talks to an alias in one config file (`deploy/litellm.yaml`). Moving to a provider with a signed ZDR agreement, or to a model you host yourself, changes no application code.
5. **Permissions apply before the model is called.** Retrieval is filtered by journal membership (and again by database row-level security), so text the user may not see is never put in a prompt.

## Where data goes

| Data | Where it lives | Leaves your server? |
|---|---|---|
| Uploaded files (PDF, DOCX, text, email) | Storage volume on your server, keyed by content hash | No |
| Extracted text, chunks, vectors, tickets, users | Your Postgres | No |
| **Document text at indexing time** | Sent to the embedding model to compute vectors | **Yes** (to the model provider) |
| **A question + the retrieved passages** | Sent to the chat model to write the answer | **Yes** (to the model provider) |
| Answer cache | Server memory only: up to 256 entries, 1 hour TTL, never written to disk, cleared on restart | No |
| "Recent questions" list in the UI | The user's own browser (`localStorage`) | No |
| Application and proxy logs | Request metadata, IDs, tool names, durations. **No question or answer text:** questions travel in request bodies, and because the Ask page address carries the question (so it can be shared), the app strips query strings from its access log and the production proxy drops the request path from its own (`app/core/logging.py`, `compose.prod.yml`) | No |
| Sign-in | Your Keycloak (self-hosted) | No |

The model gateway (LiteLLM) is configured with no database and no logging callbacks, so it does not persist prompts or responses.

## What the model provider says

The default provider is DeepInfra, with open-weight models (`BAAI/bge-m3` for embeddings; Llama models for chat). Its published data-privacy page ([docs.deepinfra.com/account/data-privacy](https://docs.deepinfra.com/account/data-privacy)) states, in summary:

- Input data is not written to disk during inference; it exists in memory while the request is processed.
- Output data is not stored; it is deleted from memory once returned.
- The content of requests is not logged; only debugging metadata (request ID, cost, sampling parameters).
- Submitted data is not used to train models, except for Google or Anthropic models, which follow those companies' own policies. **Resolve uses neither.**
- Exceptions on that page: image-generation outputs and the bulk-inference API may be held briefly. **Resolve uses neither.**

Two honest caveats. First, that page describes the provider's practice and does not use the label "zero data retention" for it; it is not the same as a signed contract. Second, third-party sites repeat SOC 2 and ISO claims; verify those on the provider's own trust page before relying on them. **For a regulated or contractual ZDR guarantee, ask the provider for a data processing agreement and written ZDR terms, or use one of the options below.**

## The privacy ladder

| Level | What you do | What leaves your network |
|---|---|---|
| 1. Default | Use the provider as configured; rely on its published policy | Questions + retrieved passages; document text at indexing |
| 2. Contractual ZDR | Get a DPA with written ZDR terms from the provider, or point the `embed` / `chat-*` aliases in `deploy/litellm.yaml` at a provider that offers them | Same data, under a contract |
| 3. Fully private | Run open-weight models yourself (for example with vLLM or Ollama) behind the same LiteLLM aliases | **Nothing** |

Levels 2 and 3 are configuration changes. Embedding size must match (`EMBEDDING_DIM`, 1024 for `bge-m3`); a different size needs a migration and re-index.

## What Resolve does not do yet (be aware)

- **No PII redaction** before text is sent to the model (Microsoft Presidio is on the roadmap).
- **No delete/purge endpoints** yet, so there is no in-app way to honour an author's erasure request; today it takes a database operation.
- **No audit table** for web actions (MCP calls are logged with tool, client and outcome).
- **No encryption of stored files or fields** beyond what your disk/database setup provides. Use an encrypted volume and encrypted backups.
- **Retrieved text appears in the answer panel and in tickets** by design: tickets are the one place a question is deliberately stored, so people can build the knowledge base.
- Prompt-injection hardening is prompt-level (sources are labelled as data) plus citation verification; it has not been red-teamed.

## Checklist for a security review

- [ ] Choose the privacy level above and record it.
- [ ] Obtain the provider's DPA / ZDR terms if level 2.
- [ ] Put the server behind HTTPS (`compose.prod.yml` does this with automatic certificates).
- [ ] Replace every dev secret; use real user accounts (the dev realm's shared password is for local use only).
- [ ] Encrypt the disk and the backups; restrict the Keycloak admin console (the production setup limits it to the server itself).
- [ ] Decide retention: how long closed tickets and old document versions are kept, and how an erasure request is handled.
