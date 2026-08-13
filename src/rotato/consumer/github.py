"""`rotato github-token` — mint a short-lived GitHub App installation token.

The stored secret is the App private key (PEM), not a usable credential. We
fetch it, sign a short-lived RS256 JWT, and exchange it for an installation
access token (~1h). The PEM stays in memory; only the minted token is returned.

Deps: pyjwt[crypto] (RS256 signing) + httpx2 (already a rotato dependency).
"""

import time

import httpx2
import jwt

from rotato.consumer import fetch

DEFAULT_API = "https://api.github.com"


def mint_token(
    pem_name_or_uuid: str,
    app_id: str,
    installation_id: str,
    api: str = DEFAULT_API,
) -> str:
    pem = fetch.fetch_value(pem_name_or_uuid)

    # iat backdated 60s for clock skew, exp +9min (GitHub caps app JWTs at 10).
    # iss is the App ID or Client ID; GitHub accepts either as a string.
    now = int(time.time())
    token = jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        pem,
        algorithm="RS256",
    )

    resp = httpx2.post(
        f"{api}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]
