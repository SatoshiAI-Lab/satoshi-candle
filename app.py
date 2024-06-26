import asyncio
from typing import Any, Callable, Coroutine, NoReturn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from utils.middleware import RealIPMiddleware, inject as inject_client
from contextlib import asynccontextmanager
from candle import CandleManager
from utils.logger import logger, APP_TITLE
import time
import sys




def startup_done(task: asyncio.Task[None]):
    try: task.result()
    except asyncio.CancelledError: pass
    except: logger.exception(f"Initializing the {task.get_name()} caused an exception.")


startup_list: list[Callable[[], Coroutine[Any, Any, None | NoReturn]]] = []
exit_list: list[Callable[[], Coroutine[Any, Any, None | NoReturn]]] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    for startup_coro_func in startup_list:
        task = asyncio.create_task(startup_coro_func(), name=startup_coro_func.__name__)
        task.add_done_callback(startup_done)
    # Running
    yield
    # Shutdown
    await asyncio.gather(*[exit_coro_func() for exit_coro_func in exit_list], return_exceptions=True)


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

def on_shutdown(func: Callable[[], Coroutine[Any, Any, None] | Coroutine[Any, Any, NoReturn]]):
    """
    Decorator to add a function to be run on shutdown.
    """
    exit_list.append(func)
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
        try:
            await ws.close(code, reason)
            ws_block: dict[str, Any] = self._clients.pop(ws)
            if ws_block['manager'] and hasattr(ws_block['manager'], 'disconnect'):
                await ws_block['manager'].disconnect(ws)
        except: pass

    async def disconnect_all(self):
        for ws in self._clients.copy():
            await self.disconnect(ws)

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
                if ws_block['ts'] + 60 < time.time():
                    try:
                        if ws.client_state == WebSocketState.CONNECTED:
                            await self.disconnect(ws, 1006, 'Heartbeat Timeout')
                    except WebSocketDisconnect: pass
                    except Exception as e:
                        logger.error(f"Error while closing WebSocket: {e}")
            await asyncio.sleep(30)

    async def broadcast(self):
        while True:
            ts = time.time()
            try:
                await CandleManager.broadcast()
            except Exception as e:
                logger.exception(f"Error while broadcasting: {e}")
            now = time.time()
            if now - ts < 60:
                await asyncio.sleep(60 - now % 60)


manager = WebSocketManager()

@on_startup
async def start_heartbeat():
    asyncio.create_task(manager.heartbeat(), name='HeartbeatLoop')
    asyncio.create_task(manager.broadcast(), name='BroadcastLoop')


@on_shutdown
async def stop_all_connections():
    await manager.disconnect_all()


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    inject_client(ws)
    try:    
        await ws.send_json({
            'type': 'notice',
            'message': 'Connected',
            'ip': ws.state.client.host,
            'port': ws.state.client.port,
        })
        while True:
            message = await ws.receive_json()
            if 'type' not in message:
                await ws.send_json({
                    'type': 'error',
                    'message': 'No message type'
                })
            else:
                await manager.message_handle(ws, message)
    except WebSocketDisconnect as e:
        if e.code > 1001 and e.reason:
            logger.warning(f"[{ws.state.client}] Connection closed unexpectedly: {e.code} {e.reason}")
    finally:
        await manager.disconnect(ws)
