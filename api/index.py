"""ADCOS Vercel entry — DIAGNOSTIC build (temporary; never merge).

Renders the assembly/import traceback in the response body so the
invocation failure can be root-caused from outside the platform.
The production shape is restored by the fix that follows the
diagnosis.
"""
import traceback


def _diagnostic_app(error_text):
    def app(scope, receive, send):
        payload = ("DIAGNOSTIC BUILD — assembly failed\n\n" + error_text).encode("utf-8")
        if scope.get("type") == "lifespan":
            while True:
                message = receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        async def _run():
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            })
            await send({"type": "http.response.body", "body": payload})
        import asyncio
        asyncio.get_event_loop().run_until_complete(_run())
    return app


try:
    from runtime.wiring import build_app_from_env
    app = build_app_from_env()
except BaseException:
    app = None
    _error_text = traceback.format_exc()


if app is None:
    app = _diagnostic_app(_error_text)
