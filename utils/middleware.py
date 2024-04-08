from fastapi import WebSocket
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


def inject(ws: WebSocket):
    cf_connecting_ip = ws.headers.get('CF-Connecting-IP')
    xreal_ip = ws.headers.get('X-Real-IP', ws.headers.get('X-Forwarded-For', ws.client.host).split(',')[0])
    xreal_port = int(ws.headers.get('X-Real-Port', ws.headers.get('X-Forwarded-Port', ws.client.port) or 0))
    real_ip = cf_connecting_ip or xreal_ip
    if not real_ip or not xreal_port:
        ws.state.client = Address(ws.client.host, ws.client.port)
    else:
        ws.state.client = Address(real_ip, xreal_port)
