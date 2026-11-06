"""Derives the production Keycloak realm from the development export.

The dev realm has seeded users with a shared password and localhost redirect
URIs. The production realm instead has:

* only the public `https://app.<domain>` as a sign-in/redirect address,
* no seeded users except one administrator whose email and *temporary*
  password come from environment variables (Keycloak substitutes `${VAR}` when it
  imports the file, so no secret is written to disk or git),
* `github.com` removed from the client-registration trusted hosts.

Usage:
    python deploy/keycloak/make_prod_realm.py --domain example.com
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent


def build(domain: str) -> dict:
    realm = json.loads((HERE / "realm-export.json").read_text(encoding="utf-8"))
    app = f"https://app.{domain}"

    realm["sslRequired"] = "external"
    realm["accessTokenLifespan"] = 600

    for client in realm["clients"]:
        if client["clientId"] != "resolve-web":
            continue
        client["redirectUris"] = [f"{app}/*"]
        client["webOrigins"] = [app]
        client["attributes"]["post.logout.redirect.uris"] = f"{app}/*"

    realm["users"] = [
        {
            "username": "${RESOLVE_ADMIN_EMAIL}",
            "email": "${RESOLVE_ADMIN_EMAIL}",
            "emailVerified": True,
            "enabled": True,
            "firstName": "Resolve",
            "lastName": "Administrator",
            "credentials": [
                {
                    "type": "password",
                    "value": "${RESOLVE_ADMIN_INITIAL_PASSWORD}",
                    "temporary": True,
                }
            ],
            "requiredActions": ["UPDATE_PASSWORD"],
            "realmRoles": ["resolve-admin"],
        }
    ]

    policies = realm["components"][
        "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy"
    ]
    for policy in policies:
        if policy["providerId"] == "trusted-hosts":
            hosts = policy["config"]["trusted-hosts"]
            policy["config"]["trusted-hosts"] = [h for h in hosts if h != "github.com"]
    return realm


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--domain", required=True, help="e.g. example.com")
    args = parser.parse_args()
    target = HERE / "realm-prod.json"
    target.write_text(
        json.dumps(build(args.domain), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target}")
