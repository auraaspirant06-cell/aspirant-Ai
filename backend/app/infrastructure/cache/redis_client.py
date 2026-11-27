"""Redis cache & short-term session ring with graceful in-memory fallback."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Any

import redis.asyncio as aioredis


class CacheStore:
    """Wraps Redis when reachable and transparently degrades to an in-memory TTL store."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None
        self._redis_unavailable = False
        self._mem_kv: dict[str, tuple[str, float | None]] = {}
        self._mem_lists: dict[str, deque[str]] = defaultdict(deque)

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis_unavailable:
            return None
        if self._client is None:
            try:
                client = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.35,
                    socket_timeout=0.5,
                )
                await client.ping()
                self._client = client
            except Exception:
                self._redis_unavailable = True
                return None
        return self._client

    @property
    def mode(self) -> str:
        return "redis" if self._client and not self._redis_unavailable else "in-memory-fallback"

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = 3600) -> None:
        raw = json.dumps(value)
        client = await self._get_redis()
        if client:
            try:
                await client.set(key, raw, ex=ttl_seconds)
                return
            except Exception:
                self._redis_unavailable = True
        expires = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._mem_kv[key] = (raw, expires)

    async def get_json(self, key: str) -> Any | None:
        client = await self._get_redis()
        if client:
            try:
                raw = await client.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                self._redis_unavailable = True
        entry = self._mem_kv.get(key)
        if not entry:
            return None
        raw, expires = entry
        if expires and time.monotonic() > expires:
            del self._mem_kv[key]
            return None
        return json.loads(raw)

    async def push_short_term_turn(self, key: str, turn: dict[str, Any], max_turns: int = 20) -> None:
        raw = json.dumps(turn)
        client = await self._get_redis()
        if client:
            try:
                await client.rpush(key, raw)
                await client.ltrim(key, -max_turns, -1)
                await client.expire(key, 86400)
                return
            except Exception:
                self._redis_unavailable = True
        ring = self._mem_lists[key]
        ring.append(raw)
        while len(ring) > max_turns:
            ring.popleft()

    async def get_short_term_turns(self, key: str, limit: int = 20) -> list[dict[str, Any]]:
        client = await self._get_redis()
        if client:
            try:
                rows = await client.lrange(key, -limit, -1)
                return [json.loads(r) for r in rows]
            except Exception:
                self._redis_unavailable = True
        ring = list(self._mem_lists.get(key, ()))[-limit:]
        return [json.loads(r) for r in ring]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
