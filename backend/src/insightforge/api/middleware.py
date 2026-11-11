"""Pure-ASGI middleware (no response buffering)."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SSENoTransform:
    """Add ``no-transform`` to Cache-Control on event streams so compressing proxies
    (the Next.js server gzips by default) forward each event immediately."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ]
                is_sse = any(
                    k.lower() == b"content-type" and v.startswith(b"text/event-stream")
                    for k, v in headers
                )
                original = [
                    v for k, v in message.get("headers", []) if k.lower() == b"cache-control"
                ]
                if is_sse:
                    headers.append((b"cache-control", b"no-cache, no-transform"))
                else:
                    headers.extend((b"cache-control", v) for v in original)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped)
