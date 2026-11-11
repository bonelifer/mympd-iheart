#!/usr/bin/env python3
"""Serve iHeartRadio account favorites and public streams to myMPD."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit

from urllib.request import build_opener

from account import CONFIG, NoRedirect, credentials, request, saved_ids, sign_in

PORT = 18767
STREAM_KEYS = (
    "secure_shoutcast_stream", "shoutcast_stream",
    "secure_hls_stream", "hls_stream",
)


def station(station_id: int) -> dict:
    """Read metadata and select an MPD-compatible stream."""
    hits = request(f"/api/v2/content/liveStations/{station_id}").get("hits")
    if not hits:
        raise LookupError("Station not found")
    item = hits[0]
    streams = item.get("streams") or {}
    urls = (streams.get(key, "") for key in STREAM_KEYS)
    url = next((value for value in urls
                if value.startswith(("https://", "http://"))), "")
    return {"id": str(station_id), "name": item.get("name") or str(station_id),
            "logo": item.get("logo") or "", "url": url}


def cache_logo(item: dict, directory: Path) -> str:
    """Cache the station logo for myMPD's same-origin artwork route."""
    url = urlsplit(item["logo"])
    if url.scheme != "https" or url.netloc != "i.iheart.com":
        return ""
    try:
        with build_opener(NoRedirect()).open(url.geturl(), timeout=5) as response:
            extension = {"image/jpeg": "jpg", "image/png": "png"}.get(
                response.headers.get_content_type()
            )
            if not extension:
                return ""
            data = response.read(2_000_001)
        if not 0 < len(data) <= 2_000_000:
            return ""
        filename = f"{item['id']}.{extension}"
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
            temporary = Path(output.name)
            try:
                output.write(data)
                output.close()
                temporary.chmod(0o644)
                temporary.replace(directory / filename)
            finally:
                temporary.unlink(missing_ok=True)
        return filename
    except (OSError, ValueError):
        return ""


def search(query: str) -> list[dict]:
    """Search the public catalog for live stations."""
    params = urlencode({"keywords": query, "queryTrack": "false",
                        "queryStation": "true", "maxRows": 15})
    results = request("/api/v3/search/all?" + params)
    return [{"id": str(item["id"]), "name": item["name"]}
            for item in results["results"].get("stations", [])]


def podcast_search(query: str) -> list[dict]:
    """Search for podcast shows by title or keyword."""
    params = urlencode({"keywords": query, "podcast": "true", "maxRows": 15})
    results = request("/api/v3/search/all?" + params)
    return [{"id": str(item["id"]), "name": item["title"]}
            for item in results["results"].get("podcasts", [])]


def episodes(podcast_id: str) -> list[dict]:
    """List the 20 most recent episodes for a show."""
    result = request(f"/api/v3/podcast/podcasts/{podcast_id}/episodes?limit=20")
    return [{"id": str(item["id"]), "name": item["title"]}
            for item in result["data"]]


def episode(episode_id: str) -> dict:
    """Resolve an episode audio URL for MPD."""
    item = request(f"/api/v3/podcast/episodes/{episode_id}")["episode"]
    url = item.get("mediaUrl") or ""
    if not url.startswith(("https://", "http://")):
        raise LookupError("Episode has no audio URL")
    return {"name": item["title"], "url": url}


class Bridge(HTTPServer):
    """Hold a single upstream session for the local picker."""

    def __init__(self, address: tuple[str, int], config: Path, artwork: Path | None):
        """Read the private config before starting the listener."""
        self.config = credentials(config, prompt=False)
        self.session = None
        self.artwork = artwork
        super().__init__(address, Handler)

    def favorites(self) -> list[dict]:
        """Refresh account favorites, reauthenticating an expired session."""
        if self.session is None:
            self.session = sign_in(self.config)
        try:
            ids = saved_ids(self.session)
        except HTTPError as error:
            if error.code != 401:
                raise
            self.session = sign_in(self.config)
            ids = saved_ids(self.session)
        favorites = []
        for station_id in ids:
            try:
                favorites.append(station(station_id))
            except LookupError:
                favorites.append({"id": str(station_id),
                                  "name": f"Station {station_id}"})
            except HTTPError as error:
                if error.code != 404:
                    raise
                favorites.append({"id": str(station_id),
                                  "name": f"Station {station_id}"})
        return favorites


class Handler(BaseHTTPRequestHandler):
    """Expose read-only JSON routes for the Lua picker."""

    def do_POST(self) -> None:
        """Save a live station through a loopback myMPD client."""
        match = re.fullmatch(r"/favorites/([1-9][0-9]{0,11})", self.path)
        if not match:
            self.send_error(404)
            return
        if (self.client_address[0] != "127.0.0.1"
                or self.headers.get_content_type() != "application/json"
                or self.headers.get("Origin")):
            self.send_error(403)
            return
        try:
            if self.server.session is None:
                self.server.session = sign_in(self.server.config)
            request("/api/v3/profiles/follows/live",
                    method="PUT", headers=self.server.session,
                    payload={"liveStationId": int(match[1])})
        except HTTPError as error:
            if error.code == 401:
                self.server.session = None
            self.send_error(502, "Could not save iHeartRadio station")
            return
        except (URLError, TimeoutError, ValueError):
            self.send_error(502, "Could not save iHeartRadio station")
            return
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        """Return favorites, search results, or a stream."""
        target = urlsplit(self.path)
        try:
            match = re.fullmatch(r"/stations/([1-9][0-9]{0,11})", target.path)
            if target.path == "/stations":
                result = self.server.favorites()
            elif target.path in {"/search", "/podcasts"}:
                query = parse_qs(target.query).get("q", [""])[0].strip()
                if not 1 <= len(query) <= 100:
                    self.send_error(400, "Enter a station name or call sign")
                    return
                result = (search(query) if target.path == "/search"
                          else podcast_search(query))
            elif podcast := re.fullmatch(r"/podcasts/([1-9][0-9]{0,11})",
                                         target.path):
                result = episodes(podcast[1])
            elif selected := re.fullmatch(r"/episodes/([1-9][0-9]{0,11})",
                                          target.path):
                result = episode(selected[1])
            elif match:
                result = station(int(match[1]))
                if not result["url"]:
                    self.send_error(404, "No playable stream")
                    return
                if self.server.artwork:
                    result["artFile"] = cache_logo(result, self.server.artwork)
            else:
                self.send_error(404)
                return
        except LookupError:
            self.send_error(404, "Station not found")
            return
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            self.send_error(502, "iHeartRadio request failed")
            return

        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Start the bridge on loopback unless another address is requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", type=Path, default=CONFIG)
    parser.add_argument("-l", "--listen", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=PORT)
    parser.add_argument("--artwork-dir", type=Path)
    args = parser.parse_args()
    try:
        server = Bridge((args.listen, args.port), args.config.expanduser(),
                        args.artwork_dir)
    except (OSError, ValueError):
        parser.exit(1, "Could not open the private config or bind the bridge.\n")
    with server:
        print(f"iHeartRadio bridge listening on {args.listen}:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
