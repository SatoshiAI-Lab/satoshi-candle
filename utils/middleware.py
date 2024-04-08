from fastapi.datastructures import Address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RealIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # if not request.client: return await call_next(request)
        cf_connecting_ip = request.headers.get('CF-Connecting-IP')
        xreal_ip = request.headers.get('X-Real-IP', request.headers.get('X-Forwarded-For', '').split(',')[0])
        xreal_port = int(request.headers.get('X-Real-Port', request.headers.get('X-Forwarded-Port', 0) or 0))

        real_ip = cf_connecting_ip or xreal_ip
        if not real_ip or not xreal_port:
            request.state.client = Address(request.client.host, request.client.port)
            return await call_next(request)
        request.state.client = Address(real_ip, xreal_port)
        return await call_next(request)
