from typing import Any
import httpx


class CexExchange:
    __DISABLE__ = False
    
    ID = 'exchange'
    order = 0
    NAME = 'CexExchange'
    NETLOC = 'example.com'
    PREFIX = ''
    INFO_URI = ''
    INFO_PATH = '' # 
    BASE = 'base'
    QUOTE = 'quote'
    QUOTE_DEFAULT = 'USDT'
    KLINE_URI = ''
    KLINE_PATH = ''
    KLINE_MAPPER: dict[str, int | str | None] = {
        '_ts': '',
        'open': '',
        'close': '',
        'high': '',
        'low': '',
        'volume': None,
        'turnover': None
    } # kline_value_path
    INFO_QUERY: dict[str, str] | None = None
    KLINE_QUERY: dict[str, str] = {}
    KLINE_QUERY_SYMBOL_PARAM = 'symbol'
    KLINE_QUERY_START_PARAM = ''
    KLINE_QUERY_LIMIT_PARAM = ''
    KLINE_QUERY_INTERVAL_PARAM = ''
    KLINE_INTERVAL_MAPPER = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d',
        'smallest': '1m',
        None: '1m'
    }
    TS_UNIT = 0 # 0 (seconds), 1 (milliseconds)
    
    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        return True
    
    @property
    def infourl(self):
        return f"https://{self.NETLOC}{self.PREFIX}{self.INFO_URI}"
    
    @property
    def infopath(self):
        return list(filter(None, self.INFO_PATH.split('->')))
    
    @property
    def klineurl(self):
        return f"https://{self.NETLOC}{self.PREFIX}{self.KLINE_URI}"
    
    @property
    def klinepath(self):
        return list(filter(None, self.KLINE_PATH.split('->')))

    @staticmethod
    def symbol_name(base: str, quote: str):
        return f"{base}-{quote}"

    @staticmethod
    def time_fix(_ts: int | str):
        ts = int(_ts)
        if ts <= 0xFFFFFFFF: ts *= 1000
        return ts

    @staticmethod
    def kline_key_name_mapper(key: str):
        if key in ('_ts', 'timestamp'): return 'timestamp'
        return key

    @classmethod
    def kline_map(cls, data: list | dict):
        return {
            cls.kline_key_name_mapper(name): cls.time_fix(data[path]) if name.startswith('_') else (float(data[path]) if path else 0.0)
            for name, path in cls.KLINE_MAPPER.items()
        }

    async def fetch(self, base: str, quote: str, start: int | None = None, limit: int | None = None, interval: str | None = None):
        query_params = self.KLINE_QUERY.copy()
        query_params[self.KLINE_QUERY_SYMBOL_PARAM] = self.symbol_name(base, quote)
        if limit and self.KLINE_QUERY_LIMIT_PARAM:
            query_params[self.KLINE_QUERY_LIMIT_PARAM] = str(limit)
        if start and self.KLINE_QUERY_START_PARAM:
            query_params[self.KLINE_QUERY_START_PARAM] = str(start)
        if interval and self.KLINE_QUERY_INTERVAL_PARAM and self.KLINE_INTERVAL_MAPPER.get(interval):
            query_params[self.KLINE_QUERY_INTERVAL_PARAM] = self.KLINE_INTERVAL_MAPPER[interval]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.klineurl, params=query_params)
                response.raise_for_status()
                klines = response.json()
                for next in self.klinepath: klines = klines[next]
                return [self.kline_map(kline) for kline in klines]
        except Exception as e:
            raise LookupError(f"Failed to fetch latest data from {self.NAME}: {e}") from e


class Binance(CexExchange):
    ID = 'binance'
    ORDER = 0
    NAME = 'Binance'
    NETLOC = 'api.binance.com'
    PREFIX = '/api/v3'
    INFO_URI = '/exchangeInfo'
    INFO_PATH = 'symbols'
    BASE = 'baseAsset'
    QUOTE = 'quoteAsset'
    
    KLINE_URI = '/klines'
    KLINE_MAPPER = {
        '_ts': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': 5,
        'turnover': 7
    }
    
    KLINE_QUERY = dict(interval='1m')
    KLINE_QUERY_LIMIT_PARAM = 'limit'
    KLINE_QUERY_INTERVAL_PARAM = 'interval'
    TS_UNIT = 1
    COMSUMER = 200
    RATE_SPEED = 0.5
    
    def symbol_name(self, base: str, quote: str):
        return f"{base}{quote}"
    
    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        base: str = symbol[cls.BASE]
        status: str = symbol['status']
        if base.endswith('UP') or base.endswith('DOWN'): return False
        if status != 'TRADING' or not symbol['isSpotTradingAllowed']: return False
        return True


class Okx(CexExchange):
    ID = 'okx'
    ORDER = 1
    NAME = 'Okx'
    NETLOC = 'www.okx.com'
    PREFIX = '/api/v5'
    INFO_URI = '/public/instruments'
    INFO_PATH = 'data'
    BASE = 'baseCcy'
    QUOTE = 'quoteCcy'
    INFO_QUERY = dict(instType='SPOT')
    
    KLINE_URI = '/market/index-candles'
    KLINE_PATH = 'data'
    KLINE_MAPPER = {
        '_ts': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': None,
        'turnover': None
    }
    KLINE_QUERY_SYMBOL_PARAM = 'instId'
    KLINE_QUERY_LIMIT_PARAM  = 'limit'
    KLINE_QUERY_INTERVAL_PARAM = 'bar'
    KLINE_INTERVAL_MAPPER = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1H',
        '4h': '4H',
        '1d': '1D',
        'smallest': '1m',
        None: '1m'
    }
    TS_UNIT = 1
    COMSUMER = 10
    
    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        if symbol['state'] != 'live': return False
        return True


class KuCoin(CexExchange):
    ID = 'kucoin'
    ORDER = 2
    NAME = 'KuCoin'
    NETLOC = 'api.kucoin.com'
    INFO_URI = '/api/v2/symbols'
    INFO_PATH = 'data'
    BASE = 'baseCurrency'
    QUOTE = 'quoteCurrency'
    
    KLINE_URI = '/api/v1/market/candles'
    KLINE_PATH = 'data'
    KLINE_MAPPER = {
        '_ts': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': 5,
        'turnover': 6
    }
    KLINE_QUERY = dict(type='1min')
    KLINE_QUERY_START_PARAM = 'startAt'
    KLINE_QUERY_INTERVAL_PARAM = 'type'
    KLINE_INTERVAL_MAPPER = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1hour',
        '4h': '4hour',
        '1d': '1day',
        'smallest': '1min',
        None: '1min'
    }
    COMSUMER = 20
    LAST_HISTORY = 10
    
    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        base:str = symbol[cls.BASE]
        if base.endswith('UP') or base.endswith('DOWN'): return False
        return bool(symbol['enableTrading'])


class Bitget(CexExchange):
    ID = 'bitget'
    NAME = 'Bitget'
    ORDER = 3
    NETLOC = 'api.bitget.com'
    PREFIX = '/api/v2'
    
    INFO_URI = '/spot/public/symbols'
    INFO_PATH = 'data'
    BASE = 'baseCoin'
    QUOTE = 'quoteCoin'
    
    KLINE_URI = '/spot/market/candles'
    KLINE_PATH = 'data'
    KLINE_QUERY = dict(granularity='1min')
    KLINE_QUERY_LIMIT_PARAM = 'limit'
    KLINE_QUERY_INTERVAL_PARAM = 'granularity'
    KLINE_INTERVAL_MAPPER = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1h',
        '4h': '4h',
        '1d': '1day',
        'smallest': '1min',
        None: '1min'
    }
    KLINE_MAPPER = {
        '_ts': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': 5,
        'turnover': 6
    }
    
    
    def symbol_name(self, base: str, quote: str):
        return f"{base}{quote}"
    
    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        return bool(symbol['status'] == 'online')


class Mexc(CexExchange):
    ID = 'mexc'
    NAME = 'MEXC'
    ORDER = 4
    NETLOC = 'api.mexc.com'
    PREFIX = '/api/v3'
    
    INFO_URI = '/exchangeInfo'
    INFO_PATH = 'symbols'
    BASE = 'baseAsset'
    QUOTE = 'quoteAsset'
    
    KLINE_URI = '/klines'
    KLINE_MAPPER = {
        '_ts': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': 5,
        'turnover': 7
    }
    
    KLINE_QUERY = dict(interval='1m')
    KLINE_QUERY_LIMIT_PARAM = 'limit'
    KLINE_QUERY_INTERVAL_PARAM = 'interval'
    TS_UNIT = 1
    COMSUMER = 40
    
    def symbol_name(self, base: str, quote: str):
        return f"{base}{quote}"

    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        return bool(symbol['isSpotTradingAllowed'])


class Gateio(CexExchange):
    ID = 'gate.io'
    NAME = 'Gate.io'
    ORDER = 5
    NETLOC = 'api.gateio.ws'
    PREFIX = '/api/v4'
    
    INFO_URI = '/spot/currency_pairs'
    
    KLINE_URI = '/spot/candlesticks'
    KLINE_MAPPER = {
        '_ts': 0,
        'volume': 1,
        'close': 2,
        'high': 3,
        'low': 4,
        'open': 5,
        'turnover': 6
    }
    
    KLINE_QUERY = dict(interval='1m')
    KLINE_QUERY_LIMIT_PARAM = 'limit'
    KLINE_QUERY_SYMBOL_PARAM = 'currency_pair'
    KLINE_QUERY_INTERVAL_PARAM = 'interval'

    def symbol_name(self, base: str, quote: str):
        return f"{base}_{quote}"

    @classmethod
    def symbol_filter(cls, symbol: dict[str, Any]):
        status: str = symbol['trade_status']
        return status.startswith('tra')

