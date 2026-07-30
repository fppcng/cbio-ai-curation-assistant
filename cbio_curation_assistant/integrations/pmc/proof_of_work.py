"""PMC proof-of-work challenge parsing and solving."""

from __future__ import annotations

import hashlib
import http.cookiejar
import re
from urllib.parse import urlparse


POW_MAX_ITERATIONS = 20_000_000


def parse_proof_of_work_challenge(
    html: str,
) -> tuple[str, int, str, str] | None:
    challenge = re.search(r'POW_CHALLENGE\s*=\s*"([^"]+)"', html)
    difficulty = re.search(r'POW_DIFFICULTY\s*=\s*"([^"]+)"', html)
    cookie_name = re.search(r'POW_COOKIE_NAME\s*=\s*"([^"]+)"', html)
    cookie_path = re.search(r'POW_COOKIE_PATH\s*=\s*"([^"]+)"', html)
    if not challenge or not difficulty or not cookie_name:
        return None
    return (
        challenge.group(1),
        int(difficulty.group(1)),
        cookie_name.group(1),
        cookie_path.group(1) if cookie_path else "/",
    )


def solve_proof_of_work_nonce(
    challenge: str,
    difficulty: int,
    *,
    max_iterations: int = POW_MAX_ITERATIONS,
) -> int:
    prefix = "0" * difficulty
    for nonce in range(max_iterations):
        digest = hashlib.sha256(
            f"{challenge}{nonce}".encode("utf-8")
        ).hexdigest()
        if digest.startswith(prefix):
            return nonce
    raise ValueError(
        "PMC proof-of-work challenge was not solved within the iteration limit."
    )


def set_proof_of_work_cookie(
    cookie_jar: http.cookiejar.CookieJar,
    url: str,
    name: str,
    value: str,
    path: str,
) -> None:
    domain = urlparse(url).hostname or "pmc.ncbi.nlm.nih.gov"
    cookie = http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=False,
        domain_initial_dot=False,
        path=path or "/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
    cookie_jar.set_cookie(cookie)


__all__ = [
    "POW_MAX_ITERATIONS",
    "parse_proof_of_work_challenge",
    "set_proof_of_work_cookie",
    "solve_proof_of_work_nonce",
]
