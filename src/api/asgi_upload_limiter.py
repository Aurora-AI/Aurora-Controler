"""
EXRS — Middleware ASGI de limite de upload de streaming de rede.
Garante interrupção da transmissão e resposta única HTTP 413 quando
o acumulador de bytes de rede ultrapassar MAX_REQUEST_BYTES (26 MiB),
antes do parser multipart alocar dados excessivos em disco/RAM.
"""
import json
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 26 * 1024 * 1024  # 26 MiB (25 MiB arquivo + 1 MiB overhead multipart)


class UploadLimitExceededError(Exception):
    def __init__(self, max_bytes: int):
        super().__init__(f"Requisição excede o limite de {max_bytes // (1024 * 1024)} MiB.")
        self.max_bytes = max_bytes


class ASGIUploadLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Early check via Content-Length se presente
        headers = dict(scope.get("headers", []))
        content_length_header = headers.get(b"content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header.decode("latin1"))
                if content_length > self.max_bytes:
                    response = JSONResponse(
                        {"detail": f"Requisição excede o limite máximo permitido de {self.max_bytes // (1024 * 1024)} MiB."},
                        status_code=413
                    )
                    await response(scope, receive, send)
                    return
            except (ValueError, UnicodeDecodeError):
                pass

        # 2. Contabilização em tempo real de streaming incremental (inclusive sem Content-Length)
        received_bytes = 0
        limit_exceeded = False
        response_started = False
        limit_response_sent = False

        err_body = json.dumps(
            {"detail": f"Requisição excede o limite máximo permitido de {self.max_bytes // (1024 * 1024)} MiB."}
        ).encode("utf-8")

        async def tracking_send(message):
            nonlocal response_started, limit_response_sent
            if limit_exceeded:
                # Intercepta qualquer resposta secundária (ex: 400 do parser do Starlette ao falhar no stream)
                # e substitui com resposta única HTTP 413
                if not limit_response_sent:
                    if message["type"] == "http.response.start":
                        limit_response_sent = True
                        await send({
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(err_body)).encode("ascii")),
                            ]
                        })
                        await send({
                            "type": "http.response.body",
                            "body": err_body,
                            "more_body": False
                        })
                return

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def limited_receive():
            nonlocal received_bytes, limit_exceeded
            if limit_exceeded:
                return {"type": "http.request", "body": b"", "more_body": False}

            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self.max_bytes:
                    limit_exceeded = True
                    raise UploadLimitExceededError(self.max_bytes)
            return message

        try:
            await self.app(scope, limited_receive, tracking_send)
        except UploadLimitExceededError as exc:
            if not limit_response_sent and not response_started:
                response = JSONResponse(
                    {"detail": f"Requisição excede o limite máximo permitido de {exc.max_bytes // (1024 * 1024)} MiB."},
                    status_code=413
                )
                await response(scope, receive, send)

