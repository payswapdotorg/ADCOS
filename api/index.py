"""ADCOS Vercel entry — DIAGNOSTIC build (temporary; never merge).

Renders the assembly/import traceback in the response body so the
invocation failure can be root-caused from outside the platform.
The production shape is restored by the fix that follows the
diagnosis.
"""
import traceback

try:
    from runtime.wiring import build_app_from_env
    app = build_app_from_env()
except BaseException:
    _error_text = traceback.format_exc()

    async def app(scope, receive, send):
        payload = (
            "DIAGNOSTIC BUILD — assembly failed\n\n" + _error_text
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        })
        await send({"type": "http.response.body", "body": payload})
