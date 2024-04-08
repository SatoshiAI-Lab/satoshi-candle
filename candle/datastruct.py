from abc import ABC, abstractmethod
from pydantic import BaseModel


class Candle(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleFactory(ABC):
    def __init__(self, interval: str) -> None:
        self._interval = interval

    @property
    def interval(self) -> str:
        """
        The interval of the CandleFactory.
        """
        return self._interval

    @abstractmethod
    async def fetch_latest(self) -> list[Candle]:
        """
        Fetch the latest candle data.
        """
        pass

    @abstractmethod
    async def fetch_history(self, start: int, limit: int) -> list[Candle]:
        """
        Fetch historical candle data.
        """
        pass

    @abstractmethod
    async def check(self) -> bool:
        """
        Check if the factory is still valid.
        """
        pass


class DexCandleFactory(CandleFactory):
    def __init__(self, chain: str, address: str, pool: str | None = None, interval: str | None = None) -> None:
        super().__init__(interval or 'smallest')
        self._chain = chain
        self._address = address
        self._pool = pool or 'all'

    @property
    def chain(self) -> str:
        """
        The chain of the DEX.
        """
        return self._chain

    @property
    def address(self) -> str:
        """
        The address of the DEX Token.
        """
        return self._address

    @property
    def pool(self) -> str:
        """
        The pool of the DEX Token.
        """
        return self._pool


class CexCandleFactory(CandleFactory):
    def __init__(self, exchange: str, symbol: str, interval: str | None = None) -> None:
        super().__init__(interval or 'smallest')
        self._exchange = exchange
        self._symbol = symbol

    @property
    def exchange(self) -> str:
        """
        The exchange of the CEX.
        """
        return self._exchange

    @property
    def symbol(self) -> str:
        """
        The symbol of the CEX.
        """
        return self._symbol


dex_cls: type[DexCandleFactory] | None = None
cex_cls: type[CexCandleFactory] | None = None


def register(factory: type[DexCandleFactory | CexCandleFactory]):
    """
    Register a CandleFactory.
    """
    if issubclass(factory, DexCandleFactory):
        global dex_cls
        dex_cls = factory
    elif issubclass(factory, CexCandleFactory):
        global cex_cls
        cex_cls = factory
