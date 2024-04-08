import json as jsonlib
import redis
import os

class Cache:
    def __init__(self, host: str, password: str, port: int, db: int = 5) -> None:
        self._redis = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=False,
        )

    def get(self, key: str) -> str | None:
        data: bytes | None = self._redis.get(key)
        if data is None: return
        return data.decode()

    def get_json(self, key: str, *, cls: type[jsonlib.JSONDecoder] | None = None) -> dict | None:
        data: bytes | None = self._redis.get(key)
        if data is None: return
        return jsonlib.loads(data, cls=cls)

    def get_int(self, key: str) -> int | None:
        data: bytes | None = self._redis.get(key)
        if data is None: return
        return int.from_bytes(data, 'big')

    def set(self, key: str, value: str | bytes, ex: int = 7200) -> None:
        self._redis.set(key, value, ex=ex)

    def set_json(self, key: str, value: dict, ex: int = 7200, *, cls: type[jsonlib.JSONEncoder] | None = None) -> None:
        self._redis.set(key, jsonlib.dumps(value, cls=cls), ex=ex)

    def set_int(self, key: str, value: int, ex: int = 7200) -> None:
        self._redis.set(key, value.to_bytes(8, 'big'), ex=ex)


cache = Cache(
    host=os.getenv('REDIS_HOST', 'localhost'),
    password=os.getenv('REDIS_PASSWORD', ''),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 5)),
)
