import asyncio
from typing import Any, Callable, Coroutine, NoReturn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from utils.middleware import RealIPMiddleware
from contextlib import asynccontextmanager
from candle import CandleManager
import logging
import time
import sys


APP_TITLE = 'OHLCV-WS-Pusher-Server'

logger = logging.getLogger(APP_TITLE)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s][%(pathname)s:%(lineno)s]%(message)s'))
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

def startup_done(task: asyncio.Task[None]):
    try: task.result()
    except asyncio.CancelledError: pass
    except: logger.exception(f"Initializing the {task.get_name()} caused an exception.")


startup_list: list[Callable[[], Coroutine[Any, Any, None | NoReturn]]] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    for startup_coro_func in startup_list:
        task = asyncio.create_task(startup_coro_func(), name=startup_coro_func.__name__)
        task.add_done_callback(startup_done)
    # Running
    yield
    # Shutdown
    pass


app = FastAPI(title=APP_TITLE, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)
app.add_middleware(RealIPMiddleware)

def on_startup(func: Callable[[], Coroutine[Any, Any, None] | Coroutine[Any, Any, NoReturn]]):
    """
    Decorator to add a function to be run on startup.
    """
    startup_list.append(func)
    return func


class WebSocketManager:
    def __init__(self):
        self._clients: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients[ws] = {
            'ts': time.time(),
            'manager': CandleManager,
        }

    async def disconnect(self, ws: WebSocket, code: int = 1000, reason: str = 'Connection Closed'):
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close()
        ws_block: dict[str, Any] = self._clients.pop(ws)
        if ws_block['manager'] and hasattr(ws_block['manager'], 'disconnect'):
            await ws_block['manager'].disconnect(ws)

    async def message_handle(self, ws: WebSocket, message: dict[str, Any]):
        ws_block: dict[str, Any] = self._clients[ws]
        if message['type'] == 'ping':
            await ws.send_json({'type': 'pong'})
            ws_block['ts'] = time.time()
        elif ws_block['manager'] and hasattr(ws_block['manager'], 'message_handle'):
            await ws_block['manager'].message_handle(ws, message)

    async def heartbeat(self):
        while True:
            for ws, ws_block in self._clients.copy().items():
                if ws_block['ts'] + 300 < time.time():
                    try:
                        if ws.client_state == WebSocketState.CONNECTED:
                            await self.disconnect(ws, 1006, 'Heartbeat Timeout')
                    except WebSocketDisconnect: pass
                    except Exception as e:
                        logger.error(f"Error while closing WebSocket: {e}")
            await asyncio.sleep(30)


manager = WebSocketManager()

@on_startup
async def start_heartbeat():
    asyncio.create_task(manager.heartbeat(), name='HeartbeatLoop')


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    ip = ws.headers.get('x-real-ip', ws.headers.get('cf-connecting-ip', ws.client.host))
    port = ws.headers.get('x-real-port', ws.client.port)
    await manager.connect(ws)
    try:    
        await ws.send_json({'type': 'notice', 'message': 'Connected'})
        while True:
            message = await ws.receive_json()
            if 'type' not in message:
                await ws.send_json({'type': 'error', 'message': 'No message type'})
            else:
                await manager.message_handle(ws, message)
    except WebSocketDisconnect as e:
        if e.code > 1001 and e.reason:
            logger.warning(f"[{ip}:{port}] Connection closed unexpectedly: {e.code} {e.reason}")
    finally:
        await manager.disconnect(ws)
