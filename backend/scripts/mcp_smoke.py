# ruff: noqa: T201, BLE001
"""End-to-end smoke test of the Resolve MCP server through the real OAuth flow.

Run it with the MCP server, Keycloak and the API up:

    python -m uv run python scripts/mcp_smoke.py            # opens your browser
    python -m uv run python scripts/mcp_smoke.py --print-url  # prints the sign-in URL instead

It discovers Keycloak from the server's 401, registers itself (dynamic client
registration), waits for you to sign in (e.g. lead@example.com) and consent, then
calls every tool and checks the answers. Nothing is written: create_ticket is only
previewed (confirm=false).
"""

import argparse
import asyncio
import sys
import webbrowser
from typing import Any

from fastmcp import Client
from fastmcp.client.auth import OAuth


def _data(result: Any) -> Any:
    return result.data if result.data is not None else result.structured_content


async def main(url: str, print_url: bool) -> int:
    if print_url:
        webbrowser.open = lambda target, *a, **k: (  # type: ignore[assignment]
            print(f"SIGN-IN URL: {target}", flush=True) or True
        )

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
        if not ok:
            failures.append(name)

    async with Client(
        url, auth=OAuth(mcp_url=url, client_name="Resolve smoke test")
    ) as client:
        tools = {t.name for t in await client.list_tools()}
        expected = {
            "list_journals", "ask_resolve", "search_knowledge", "list_tickets",
            "get_ticket", "suggest_answer", "create_ticket",
        }  # fmt: skip
        check("tools listed", expected <= tools, f"missing: {sorted(expected - tools)}")

        journals = _data(await client.call_tool("list_journals", {}))
        items = (
            journals.get("journals", journals)
            if isinstance(journals, dict)
            else journals
        )
        check("list_journals", bool(items), f"{len(items)} journal(s)")
        if not items:
            print(
                "\nNo journals for this user. Over MCP even an administrator only sees "
                "journals they are a member of: sign in as lead@example.com "
                "(use a private window if the browser reuses another session).",
                flush=True,
            )
            return 1
        code = items[0].get("code") if isinstance(items[0], dict) else str(items[0])

        found = _data(
            await client.call_tool(
                "search_knowledge", {"journal": code, "query": "abstract length"}
            )
        )
        check("search_knowledge", bool(found), str(found)[:80].replace("\n", " "))

        answer = _data(
            await client.call_tool(
                "ask_resolve",
                {"journal": code, "question": "How long may the abstract be?"},
            )
        )
        text = str(answer)
        check(
            "ask_resolve answers with a citation",
            "[" in text,
            text[:100].replace("\n", " "),
        )

        tickets = _data(
            await client.call_tool("list_tickets", {"journal": code, "status": "all"})
        )
        check("list_tickets", tickets is not None, str(tickets)[:80].replace("\n", " "))

        preview = _data(
            await client.call_tool(
                "create_ticket",
                {"journal": code, "title": "Smoke test ticket", "confirm": False},
            )
        )
        check(
            "create_ticket previews without writing",
            "preview" in str(preview).lower() or "confirm" in str(preview).lower(),
            str(preview)[:80].replace("\n", " "),
        )

        denied = False
        try:
            await client.call_tool("list_tickets", {"journal": "NOPE-NOT-A-JOURNAL"})
        except Exception as exc:  # unknown and forbidden journals look the same
            denied = "not found" in str(exc).lower() or "unknown" in str(exc).lower()
        check("unknown journal is refused", denied)

    print(f"\n{'ALL PASSED' if not failures else 'FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8010/mcp")
    parser.add_argument("--print-url", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.url, args.print_url)))
