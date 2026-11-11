#!/usr/bin/env python3
"""Save iHeartRadio credentials locally and check the saved-station API."""

import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4
import warnings


API = "https://us.api.iheart.com"
CONFIG = Path.home() / ".config" / "mympd-iheart" / "test-account.json"
PAGE_SIZE = 15


class NoRedirect(HTTPRedirectHandler):
    """Keep passwords and session headers on the original API host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Decline redirects."""
        return None


def credentials(path: Path, *, prompt: bool = True) -> dict:
    """Read saved credentials or prompt and save a private config."""
    if prompt:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if not prompt:
            raise
        fd = None

    if fd is not None:
        with os.fdopen(fd, encoding="utf-8") as config:
            info = os.fstat(config.fileno())
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise ValueError("Config must be a private regular file you own.")
            data = json.load(config)
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), str) or not data[key]
            for key in ("userName", "password", "deviceId")
        ):
            raise ValueError("Config is missing required credential fields.")
        return data

    email = input("iHeartRadio email: ").strip()
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("iHeartRadio password: ")
    if not email or not password:
        raise ValueError("Email and password are required.")

    data = {"userName": email, "password": password, "deviceId": str(uuid4())}
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as config:
        temporary = Path(config.name)
        try:
            json.dump(data, config)
            config.close()
            os.link(temporary, path)
        finally:
            temporary.unlink()
    return data


def request(path: str, *, form=None, headers=None, method=None, payload=None) -> dict:
    """Return an API JSON object without printing request or response secrets."""
    body = urlencode(form).encode("utf-8") if form is not None else None
    if payload is not None:
        body = json.dumps(payload).encode()
    req = Request(API + path, data=body, headers=headers or {}, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    with build_opener(NoRedirect()).open(req, timeout=15) as response:
        if response.status in (201, 204):
            return {}
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("Unexpected API response format.")
    return data


def sign_in(data: dict) -> dict[str, str]:
    """Exchange saved credentials for iHeartRadio session headers."""
    session = request("/api/v1/account/login", form={
        "userName": data["userName"],
        "password": data["password"],
        "deviceId": data["deviceId"],
        "deviceName": "myMPD iHeartRadio account test",
        "host": "webapp.US",
        "setCurrentStreamer": "false",
    })
    profile_id = session.get("profileId")
    session_id = session.get("sessionId")
    if not profile_id or not isinstance(session_id, str) or not session_id:
        raise ValueError("The response did not contain a profile and session.")
    return {
        "X-IHR-Profile-ID": str(profile_id),
        "X-IHR-Session-ID": session_id,
    }


def saved_ids(headers: dict) -> list[int]:
    """Read every page and return the followed live station IDs."""
    ids = []
    for offset in range(0, 1500, PAGE_SIZE):
        page = f"?limit={PAGE_SIZE}&offset={offset}"
        result = request("/api/v3/profiles/follows/live" + page,
                         headers=headers)
        rows = result.get("data")
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or type(row.get("liveStationId")) is not int
            for row in rows
        ):
            raise ValueError("Unexpected saved-station response format.")
        ids.extend(row["liveStationId"] for row in rows)
        if len(rows) < PAGE_SIZE:
            return ids
    raise ValueError("Saved-station pagination limit reached.")


def main() -> int:
    """Run the explicitly selected account check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--check", action="store_true",
                        help="sign in and list saved live station IDs")
    parser.add_argument("-f", "--config", type=Path, default=CONFIG,
                        help="private JSON file for credentials")
    args = parser.parse_args()
    if not args.check:
        parser.print_help()
        return 0

    stage = "Credential setup"
    try:
        data = credentials(args.config.expanduser())
        stage = "Sign-in"
        headers = sign_in(data)
        print("Sign-in succeeded.")
        stage = "Saved-station lookup"
        ids = saved_ids(headers)
        print(f"Saved live station IDs ({len(ids)}): "
              + (", ".join(map(str, ids)) or "none"))
    except HTTPError as error:
        print(f"{stage} failed (HTTP {error.code}).", file=sys.stderr)
        return 1
    except (OSError, URLError, ValueError, EOFError, getpass.GetPassWarning):
        print(f"{stage} failed. Check the local config or API response.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
