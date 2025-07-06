from fastapi import APIRouter
import inspect

class MCPServer:
    """Minimal stub of the fastapi-mcp library used for tests."""
    def __init__(self, app, mount_path: str = "/mcp", **kwargs):
        self.router = APIRouter()
        app.include_router(self.router, prefix=mount_path)

    def tool(self, path: str | None = None, methods: list[str] | None = None):
        """Decorator to expose a function as an API endpoint."""
        methods = methods or ["POST"]

        def decorator(func):
            endpoint = path or func.__name__

            async def endpoint_func(*args, **kwargs):
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                return result

            self.router.api_route(f"/{endpoint}", methods=methods)(endpoint_func)
            return func

        return decorator

def add_mcp_server(app, **kwargs):
    """Return a basic MCPServer instance and mount it."""
    return MCPServer(app, **kwargs)
