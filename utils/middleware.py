from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RealIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.client: return await call_next(request)
        xreal_ip = request.headers.get('X-Real-IP', request.client.host)
        xreal_port = int(request.headers.get('X-Real-Port', request.client.port))
        cf_connecting_ip = request.headers.get('CF-Connecting-IP')

        real_ip = cf_connecting_ip or xreal_ip
        request.scope['client'] = (real_ip, xreal_port)

        return await call_next(request)
