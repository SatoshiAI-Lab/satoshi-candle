from typing import Any
from . import datastruct as ds
import json as jsonlib
import httpx


NETWORKS_SRC = jsonlib.load(open('gecko-networks.json', 'r', encoding='utf-8'))
NETWORKS = {
    network['id']: {
        'id': network['id'],
        'name': network['attributes']['name'],
        'slug': network['attributes']['coingecko_asset_platform_id'],
    }
    for network in NETWORKS_SRC
}

INTERVALS = {
    '1m': (1, 'minute'),
    '5m': (5, 'minute'),
    '15m': (15, 'minute'),
    '1h': (1, 'hour'),
    '4h': (4, 'hour'),
    '1d': (1, 'day'),
    'smallest': (1, 'minute'),
    None: (1, 'minute'),
}

class DexViewer:
    ID = 'geckoterminal'
    BASE_URL = 'https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool}/ohlcv/{timeframe}'
    START_PARAM = 'before_timestamp'
    LIMIT_PARAM = 'limit'

    def __init__(self, network: str, pool: str, interval: str | None = None):
        self.network = network
        self.pool = pool
        if interval not in INTERVALS:
            raise ValueError('Invalid Interval')
        self.timeframe = INTERVALS[interval][1]
        self.aggregate = INTERVALS[interval][0]
        self.url = self.BASE_URL.format(network=network, pool=pool, timeframe=self.timeframe)
        self.query_params = {
            'aggregate': self.aggregate,
        }
        self.base = None
        self.quote = None

    async def fetch(self, start: int | None = None, limit: int | None = None) -> list[ds.Candle]:
        query_params = self.query_params.copy()
        if start:
            query_params[self.START_PARAM] = start
        if limit:
            query_params[self.LIMIT_PARAM] = limit
        try:
            async with httpx.AsyncClient() as client:
                for _ in range(3):
                    try:
                        response = await client.get(self.url, params=query_params)
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        continue
                else:
                    raise LookupError(f"Failed to fetch data from {self.NAME}")
                response.raise_for_status()
                results: dict[str, Any] = response.json()
                if 'error' in results:
                    raise LookupError(f"Error from {self.NAME}: {results['error']}")
                meta: dict[str, dict[str, str]] = results.get('meta', {})
                self.base = meta.get('base')
                self.quote = meta.get('quote')
                results: list[list] = results.get('data', {}).get('attributes', {}).get('ohlcv_list', [])
                if len(results) == 0:
                    raise LookupError(f"No data available for {self.NAME}")
                return [
                    ds.Candle(
                        timestamp=int(result[0]),
                        open=float(result[1]),
                        high=float(result[2]),
                        low=float(result[3]),
                        close=float(result[4]),
                        volume=float(result[5]),
                    )
                    for result in results
                ]
        except LookupError: raise
        except Exception as e:
            raise LookupError(f"Error from {self.NAME}: {e}")


class DexFactory(ds.DexCandleFactory):
    def __init__(self, network: str, token: str, pool: str, interval: str | None = None) -> None:
        if network not in NETWORKS:
            raise ValueError('Invalid Network')
        if interval not in INTERVALS:
            raise ValueError('Invalid Interval')
        self.viewer = DexViewer(network, pool, interval)
        self.token = token
        super().__init__(self.ID, f'{network}-{pool}', interval)

    @property
    def info(self) -> dict[str, str]:
        return {
            'token': self.token,
            'base': self.viewer.base,
            'quote': self.viewer.quote,
        }

    async def check(self) -> bool:
        try:
            await self.viewer.fetch(limit=1)
            return True
        except LookupError:
            return False

    async def fetch_newest(self) -> list[ds.Candle]:
        return await self.viewer.fetch(limit=3)

    async def fetch_history(self, start: int | None = None, limit: int | None = None) -> list[ds.Candle]:
        return await self.viewer.fetch(start, limit)

    async def fetch_latest(self) -> list[ds.Candle]:
        return await self.viewer.fetch()


def init():
    ds.register(DexFactory)
