"""Mint a short-lived GitHub App installation token from a private key.

Sign a short-lived RS256 JWT with the App PEM and exchange it for an
installation access token (~1h). The caller supplies the PEM; only the minted
token is returned.

Deps: pyjwt[crypto] (RS256 signing) + httpx2 (already a rotato dependency).
"""

import time

import httpx2
import jwt

DEFAULT_API = "https://api.github.com"


def mint_token(
    pem: str,
    app_id: str,
    installation_id: str,
    api: str = DEFAULT_API,
) -> str:
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
