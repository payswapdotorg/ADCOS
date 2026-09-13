"""ADCOS Vercel entry — DIAGNOSTIC build (temporary; never merge).

The module-level ``app`` assignment keeps the @vercel/python static
entrypoint scan satisfied; the assembly runs inside a factory whose
try/except captures ANY import/assembly failure and substitutes a
renderer that returns the traceback verbatim — the invocation crash
root-caused from outside the platform.
"""
import traceback


def _make_app():
    try:
        from runtime.wiring import build_app_from_env
        return build_app_from_env()
    except BaseException:
        text = traceback.format_exc()

        async def diag(scope, receive, send):
            payload = (
                "DIAGNOSTIC BUILD — assembly failed\n\n" + text
            ).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                ],
            })
            await send({"type": "http.response.body", "body": payload})

        return diag


app = _make_app()
