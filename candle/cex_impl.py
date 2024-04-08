from . import cex, datastruct as ds
import inspect
import asyncio


cexes = {
    obj.ID: obj
    for _, obj in inspect.getmembers(cex, inspect.isclass)
    if issubclass(obj, cex.CexExchange) and obj != cex.CexExchange
}


class HTTPCEX(ds.CexCandleFactory):
    @classmethod
    async def check_first_cex(cls, base: str, quote: str, interval: str | None = None) -> cex.CexExchange | None:
        for cex_type in sorted(cexes.values(), key=lambda x: x.ORDER):
            if interval not in cex_type.KLINE_INTERVAL_MAPPER: continue
            cex = cex_type()
            try:
                klines = await cex.fetch(base, quote, limit=1, interval=interval)
                if not klines: continue
                return cex
            except LookupError: continue
        else:
            raise ValueError('No CEX can fetch the data')

    def __init__(self, exchange: str, symbol: str, interval: str | None = None) -> None:
        self.base, self.quote = symbol.split('-')
        if exchange == '*':
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(self.check_first_cex(self.base, self.quote, interval), loop)
            self.cex = future.result()
        elif exchange not in cexes:
            raise ValueError('Invalid CEX Exchange')
        else:
            if interval not in cexes[exchange].KLINE_INTERVAL_MAPPER:
                raise ValueError('Invalid CEX Interval')
            self.cex = cexes[exchange]()
        super().__init__(self.cex.ID, symbol, interval)

    async def check(self) -> bool:
        return True

    async def fetch_newest(self) -> list[ds.Candle]:
        klines = await self.cex.fetch(self.base, self.quote, limit=3, interval=self.interval)
        return [ds.Candle(**kline) for kline in klines]

    async def fetch_history(self, start: int | None = None, limit: int | None = None) -> list[ds.Candle]:
        klines = await self.cex.fetch(self.base, self.quote, start, limit, self.interval)
        return [ds.Candle(**kline) for kline in klines]

    async def fetch_latest(self) -> list[ds.Candle]:
        klines = await self.cex.fetch(self.base, self.quote, interval=self.interval)
        return [ds.Candle(**kline) for kline in klines]


def init():
    ds.register(HTTPCEX)
