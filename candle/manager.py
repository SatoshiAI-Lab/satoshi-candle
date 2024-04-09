from . import datastruct
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import logger


class CandleSenderReceiver:
    def __init__(self, tag: str, factory: datastruct.CandleFactory) -> None:
        self._tag = tag
        self._listeners: set[WebSocket] = set()
        self._factory = factory

    @property
    def tag(self) -> str:
        """
        the tag of the manager
        """
        return self._tag

    async def add_listener(self, ws: WebSocket) -> None:
        """
        Register a new listener to the manager
        """
        latest = await self._factory.fetch_latest()
        self._listeners.add(ws)
        await ws.send_json({
            'type': 'init',
            'status': 'success',
            'message': 'listening to new data',
            'tag': self.tag,
            'data': [candle.model_dump() for candle in latest]
        })

    async def check(self):
        """
        Check the tag is still valid
        """
        return await self._factory.check()

    async def pull_newest(self):
        """
        Poll the newest data from the factory once
        """
        return await self._factory.fetch_newest()

    async def pull_history(self, ws: WebSocket, start: str | int | None, limit: str | int | None) -> None:
        """
        Get historical data based on user request
        """
        try:
            history = await self._factory.fetch_history(int(start) if start else None, int(limit))
            await ws.send_json({
                'type': 'history',
                'data': [candle.model_dump() for candle in history]
            })
        except WebSocketDisconnect: raise
        except Exception as e:
            await ws.send_json({'type': 'error', 'message': f'Error while fetching history: {e}'})

    def remove_listener(self, ws: WebSocket) -> bool:
        """
        Remove a listener from the manager, and return if there are still listeners
        """
        if ws not in self._listeners:
            raise ValueError(f'Listener not found in {self.tag} tag')
        self._listeners.remove(ws)
        return len(self._listeners) > 0

    async def boardcast(self, data: list[datastruct.Candle]) -> None:
        """
        Broadcast the newly collected data to all listeners
        """
        datas = [candle.model_dump() for candle in data]
        for ws in self._listeners:
            try:
                await ws.send_json({
                    'type': 'update',
                    'data': datas
                })
            except WebSocketDisconnect: pass
            except Exception as e:
                logger.error(f'Error while sending data to {ws.state.client}: {e}')


class CandleManager:
    listeners: dict[str, CandleSenderReceiver] = {}

    @classmethod
    async def _listen(cls, ws: WebSocket, tag: str) -> None:
        mode, args = tag.split(':', 1)
        match mode:
            case 'dex':
                if tag in cls.listeners:
                    return await cls.listeners[tag].add_listener(ws)
                if datastruct.dex_cls is None:
                    raise ValueError('DEX Candle Factory not set.')
                csr = CandleSenderReceiver(tag, datastruct.dex_cls(*args.split(':')))
                if not await csr.check():
                    raise ValueError('Invalid DEX Candle Factory')
                await csr.add_listener(ws)
                cls.listeners[tag] = csr
                logger.info(f'New Listener for {tag}')
            case 'cex':
                if tag in cls.listeners:
                    return await cls.listeners[tag].add_listener(ws)
                if datastruct.cex_cls is None:
                    raise ValueError('CEX Candle Factory not set.')
                if '*' in args:
                    if getattr(datastruct.cex_cls, 'check_first_cex', None) is None:
                        raise ValueError('CEX Candle Factory not support wildcard')
                    cex: str | None = await datastruct.cex_cls.check_first_cex(*args.split(':'))
                    if cex is None:
                        raise ValueError('No CEX can fetch the data')
                    args = args.replace('*', cex, 1)
                    tag = f'cex:{args}'
                if tag in cls.listeners:
                    return await cls.listeners[tag].add_listener(ws)
                csr = CandleSenderReceiver(tag, datastruct.cex_cls(*args.split(':')))
                if not await csr.check():
                    raise ValueError('Invalid CEX Candle Factory')
                await csr.add_listener(ws)
                cls.listeners[tag] = csr
                logger.info(f'New Listener for {tag}')
            case _:
                await ws.send_json({'type': 'error', 'message': f'Invalid Tag {tag}'})

    @classmethod
    async def _unlisten(cls, ws: WebSocket, tag: str) -> None:
        if tag not in cls.listeners:
            return await ws.send_json({'type': 'notice', 'status': 'error', 'message': f'No listener for {tag}'})
        if not cls.listeners[tag].remove_listener(ws):
            del cls.listeners[tag]
            logger.info(f'Listener for {tag} removed')
        await ws.send_json({'type': 'notice', 'status': 'success', 'message': 'unlisten success', 'tag': tag})

    @staticmethod
    def get_tag(data: dict[str, str]):
        tag = data.get('tag', '')
        if not tag:
            if 'symbol' in data:
                tag = f'cex:{data["exchange"]}:{data["symbol"]}:{data.get("interval", "smallest")}'
            elif 'chain' in data:
                tag = f'dex:{data["chain"]}:{data["address"]}:{data.get("pool", "all")}:{data.get("interval", "smallest")}'
            else:
                raise ValueError('Invalid Tag')
        if ':' not in tag:
            raise ValueError('Invalid Tag')
        return tag

    @classmethod
    async def broadcast(cls) -> None:
        for tag in cls.listeners:
            data = await cls.listeners[tag].pull_newest()
            await cls.listeners[tag].boardcast(data)

    @classmethod
    async def message_handle(cls, ws: WebSocket, message: dict[str, str]) -> None:
        message_type = message.get('type')
        data = message.get('data', {})
        match message_type:
            case 'listen':
                try:
                    tag = cls.get_tag(data)
                    await cls._listen(ws, tag)
                except (ValueError, LookupError) as e:
                    return await ws.send_json({'type': 'init', 'status': 'error', 'message': str(e), 'data': []})
            case 'unlisten':
                try:
                    tag = cls.get_tag(data)
                    await cls._unlisten(ws, tag)
                except ValueError as e:
                    return await ws.send_json({'type': 'error', 'message': str(e)})
            case 'history':
                try:
                    tag = cls.get_tag(data)
                except (ValueError, LookupError) as e:
                    return await ws.send_json({'type': 'error', 'message': str(e)})
                if tag not in cls.listeners:
                    return await ws.send_json({'type': 'error', 'message': f'No listener for {tag}'})
                await cls.listeners[tag].pull_history(ws, data['start'], data.get('limit'))

    @classmethod
    async def disconnect(cls, ws: WebSocket) -> None:
        for tag in list(cls.listeners):
            if not cls.listeners[tag].remove_listener(ws):
                del cls.listeners[tag]
                logger.info(f'Listener for {tag} removed')
