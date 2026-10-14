"""Exercise the actual ASGI app without a listening socket or a portal thread.

A short timer keeps asyncio responsive in sandboxes that block socketpair wakeups.
It does not replace endpoints, storage, file handling or the HTTP middleware.
"""
import asyncio
import httpx


class ASGIClient:
    def __init__(self, app):
        self.app = app

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, path, **kwargs):
        async def run():
            async def clock():
                while True:
                    await asyncio.sleep(.01)
            timer = asyncio.create_task(clock())
            try:
                async with self.app.router.lifespan_context(self.app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://testserver') as client:
                        return await client.request(method, path, **kwargs)
            finally:
                timer.cancel()
                try:
                    await timer
                except asyncio.CancelledError:
                    pass
        return asyncio.run(run())

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)

    def put(self, path, **kwargs):
        return self.request('PUT', path, **kwargs)
