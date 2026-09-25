"""Send a notification through Bark (https://github.com/Finb/bark-server).

API: POST <server>/push with application/json; charset=utf-8
Fields used: device_key, title, body, group, url, level, isArchive.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_SERVER = "https://api.day.app"
TIMEOUT_S = 15


class PushError(RuntimeError):
    """Bark rejected the push. Never carries the device key."""


def send(
    device_key: str,
    title: str,
    body: str,
    *,
    group: str = "Canvas",
    url: str | None = None,
    level: str = "active",
    server: str = DEFAULT_SERVER,
) -> None:
    if not device_key:
        raise PushError("BARK_KEY is empty")

    payload: dict[str, object] = {
        "device_key": device_key,
        "title": title,
        "body": body,
        "group": group,
        "level": level,
        "isArchive": "1",
    }
    if url:
        payload["url"] = url

    request = urllib.request.Request(
        f"{server.rstrip('/')}/push",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            raw = response.read(4096)
    except urllib.error.HTTPError as exc:
        raise PushError(f"Bark returned HTTP {exc.code} — is BARK_KEY correct?") from None
    except urllib.error.URLError as exc:
        raise PushError(f"could not reach Bark: {exc.reason}") from None

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise PushError("Bark returned a response that was not JSON") from None

    if result.get("code") != 200:
        raise PushError(f"Bark rejected the push: {result.get('message', 'unknown error')}")
