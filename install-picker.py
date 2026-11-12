#!/usr/bin/env python3
"""Install the iHeartRadio Favorites picker using myMPD's protected JSON-RPC API."""

import argparse
import json
import os
from pathlib import Path
from shutil import copyfile
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def main():
    """Submit the bundled Lua script to the selected myMPD partition."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mympd", required=True, help="myMPD base URL")
    parser.add_argument("--partition", default="default")
    parser.add_argument("--service", default="http://127.0.0.1:18767",
                        help="Bridge URL reachable from myMPD")
    parser.add_argument("--replace", action="store_true",
                        help="Replace the installed script of the same name")
    parser.add_argument("--home-workdir", type=Path,
                        help="myMPD work directory for installing the Home tile")
    args = parser.parse_args()
    for url in (args.mympd, args.service):
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.query or parsed.fragment
                or not url.isascii() or any(ord(char) <= 32 for char in url)):
            parser.error("URLs must be HTTP(S) without credentials or queries")

    filename = "iheart.lua"
    default_service = "http://127.0.0.1:18767"
    metadata_line, _, source = Path(__file__).with_name(filename).read_text(
        encoding="utf-8"
    ).partition("\n")
    metadata = json.loads(metadata_line.removeprefix("-- "))
    source = source.replace(
        json.dumps(default_service), json.dumps(args.service.rstrip("/")), 1
    )
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "MYMPD_API_SCRIPT_SAVE",
        "params": {
            "script": metadata["name"],
            "oldscript": metadata["name"] if args.replace else "",
            "file": metadata["file"],
            "version": metadata["version"],
            "order": metadata["order"],
            "arguments": metadata["arguments"],
            "content": source,
        },
    }
    headers = {"Content-Type": "application/json"}
    if session := os.environ.get("MYMPD_SESSION"):
        headers["X-myMPD-Session"] = session
    endpoint = args.mympd.rstrip("/") + "/api/" + quote(args.partition, safe="")
    def rpc(payload):
        request = Request(endpoint, json.dumps(payload).encode(), headers)
        with urlopen(request, timeout=15) as response:
            reply = json.load(response)
        if "error" in reply or "result" not in reply:
            raise ValueError(f"myMPD rejected {payload['method']}: {reply.get('error')}")
        return reply["result"]

    try:
        launcher = None
        if args.home_workdir is not None:
            root = Path(__file__).resolve().parent
            launcher = json.loads(
                (root / "dockhand/home-launcher.json").read_text(encoding="utf-8")
            )
            image = launcher["params"]["image"]
            thumbs = args.home_workdir / "pics" / "thumbs"
            if not thumbs.is_dir():
                parser.error("--home-workdir must contain pics/thumbs")
            target = thumbs / image
            source_image = root / "assets" / image
            if target.exists():
                if target.read_bytes() != source_image.read_bytes():
                    raise ValueError(f"Home image already exists with different content: {target}")
            else:
                copyfile(source_image, target)

        rpc(payload)
        print(f"Installed {metadata['name']} in myMPD.")
        if launcher is not None:
            result = rpc(dict(jsonrpc="2.0", id=1,
                              method="MYMPD_API_HOME_ICON_LIST", params={}))
            for index, tile in enumerate(result["data"]):
                if (tile.get("cmd") == launcher["params"]["cmd"]
                        and tile.get("options") == launcher["params"]["options"]):
                    launcher["params"].update(replace=True, oldpos=index)
                    break
            rpc(launcher)
            print(f"Installed {launcher['params']['name']} Home tile.")
    except (OSError, TimeoutError, ValueError) as error:
        parser.exit(1, f"Installation failed: {error}\n")


if __name__ == "__main__":
    main()
