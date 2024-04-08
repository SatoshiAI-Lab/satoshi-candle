from . import cex, datastruct as ds
import inspect


cexes = {
    obj.ID: obj
    for _, obj in inspect.getmembers(cex, inspect.isclass)
    if issubclass(obj, cex.CexExchange) and obj != cex.CexExchange
}


class HTTPCEX(ds.CexCandleFactory):
    def __init__(self, exchange: str, symbol: str, interval: str | None = None) -> None:
        if exchange not in cexes:
            raise ValueError('Invalid CEX Exchange')
        if interval not in cexes[exchange].KLINE_INTERVAL_MAPPER:
            raise ValueError('Invalid CEX Interval')
        super().__init__(exchange, symbol, interval)
        self.base, self.quote = symbol.split('-')
        self.cex = cexes[exchange]()

    async def check(self) -> bool:
        return True

    async def fetch_history(self, start: int | None = None, limit: int | None = None) -> list[ds.Candle]:
        klines = await self.cex.fetch(self.base, self.quote, start, limit, self.interval)
        return [ds.Candle(**kline) for kline in klines]

    async def fetch_latest(self) -> list[ds.Candle]:
        klines = await self.cex.fetch(self.base, self.quote, interval=self.interval)
        return [ds.Candle(**kline) for kline in klines]


def init():
    ds.register(HTTPCEX)
