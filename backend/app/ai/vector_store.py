"""Vector embedding and dual-backend vector database adapters (Qdrant + Chroma)."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


DEFAULT_EMBED_DIM = 128


def compute_local_embedding(text: str, dim: int = DEFAULT_EMBED_DIM) -> list[float]:
    """Deterministic normalized character n-gram + token projection embedding."""
    vec = [0.0] * dim
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    if not normalized:
        return vec
    tokens = normalized.split(" ")
    features: list[str] = list(tokens)
    for tok in tokens:
        if len(tok) >= 3:
            features.extend(tok[i : i + 3] for i in range(len(tok) - 2))
    for idx in range(len(tokens) - 1):
        features.append(f"{tokens[idx]}_{tokens[idx + 1]}")
    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        weight = 1.5 if "_" in feat else (1.2 if " " not in feat and len(feat) > 3 else 0.7)
        vec[bucket] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


@dataclass(slots=True)
class VectorRecord:
    id: str
    user_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class VectorBackend(Protocol):
    backend_name: str

    def upsert(self, *, record_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None: ...
    def search(
        self, *, user_id: str, query: str, limit: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorRecord]: ...
    def delete(self, *, record_id: str) -> None: ...


class InMemoryVectorStore:
    """Zero-dependency cosine similarity store used as fallback or fast test double."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._items: dict[str, tuple[str, str, list[float], dict[str, Any]]] = {}

    def upsert(self, *, record_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None:
        vec = compute_local_embedding(text)
        self._items[record_id] = (user_id, text, vec, dict(metadata))

    def search(
        self, *, user_id: str, query: str, limit: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorRecord]:
        qvec = compute_local_embedding(query)
        hits: list[VectorRecord] = []
        for rec_id, (uid, text, vec, meta) in self._items.items():
            if uid != user_id:
                continue
            if filters and any(meta.get(k) != v for k, v in filters.items()):
                continue
            score = cosine_similarity(qvec, vec)
            hits.append(VectorRecord(id=rec_id, user_id=uid, text=text, metadata=meta, score=score))
        hits.sort(key=lambda r: r.score, reverse=True)
        return hits[:limit]

    def delete(self, *, record_id: str) -> None:
        self._items.pop(record_id, None)


class QdrantVectorStore:
    """Qdrant vector store supporting remote Qdrant HTTP/gRPC or embedded ':memory:' mode."""

    backend_name = "qdrant"

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str = "aspirant_memory",
        in_memory: bool = False,
    ) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._collection = collection_name
        if in_memory or not url:
            self._client = QdrantClient(":memory:")
        else:
            self._client = QdrantClient(url=url, api_key=api_key or None, timeout=3.0)

        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=DEFAULT_EMBED_DIM, distance=Distance.COSINE),
            )

    def upsert(self, *, record_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None:
        from qdrant_client.models import PointStruct

        vec = compute_local_embedding(text)
        payload = {"user_id": user_id, "text": text, **metadata}
        point_uuid = hashlib.md5(record_id.encode("utf-8")).hexdigest()
        self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=point_uuid, vector=vec, payload={"external_id": record_id, **payload})],
        )

    def search(
        self, *, user_id: str, query: str, limit: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorRecord]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        for k, v in (filters or {}).items():
            conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))

        qvec = compute_local_embedding(query)
        response = self._client.query_points(
            collection_name=self._collection,
            query=qvec,
            query_filter=Filter(must=conditions),
            limit=limit,
        )
        results: list[VectorRecord] = []
        for pt in response.points:
            payload = dict(pt.payload or {})
            text = str(payload.pop("text", ""))
            uid = str(payload.pop("user_id", user_id))
            ext_id = str(payload.pop("external_id", pt.id))
            results.append(
                VectorRecord(id=ext_id, user_id=uid, text=text, metadata=payload, score=float(pt.score))
            )
        return results

    def delete(self, *, record_id: str) -> None:
        from qdrant_client.models import PointIdsList

        point_uuid = hashlib.md5(record_id.encode("utf-8")).hexdigest()
        self._client.delete(
            collection_name=self._collection,
            points_selector=PointIdsList(points=[point_uuid]),
        )


class ChromaVectorStore:
    """Chroma vector store supporting PersistentClient, EphemeralClient, or HttpClient."""

    backend_name = "chroma"

    def __init__(
        self,
        *,
        persist_dir: str | None = None,
        host: str | None = None,
        collection_name: str = "aspirant_memory",
        ephemeral: bool = False,
    ) -> None:
        import chromadb

        if host:
            self._client = chromadb.HttpClient(host=host)
        elif ephemeral or not persist_dir:
            self._client = chromadb.Client()
        else:
            self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, *, record_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None:
        vec = compute_local_embedding(text)
        flat_meta: dict[str, str | int | float | bool] = {"user_id": user_id}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                flat_meta[k] = v
            else:
                flat_meta[k] = str(v)
        self._collection.upsert(
            ids=[record_id],
            embeddings=[vec],
            documents=[text],
            metadatas=[flat_meta],
        )

    def search(
        self, *, user_id: str, query: str, limit: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorRecord]:
        where: dict[str, Any] = {"user_id": user_id}
        for k, v in (filters or {}).items():
            where[k] = v
        qvec = compute_local_embedding(query)
        raw = self._collection.query(query_embeddings=[qvec], n_results=limit, where=where)
        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        results: list[VectorRecord] = []
        for idx, rec_id in enumerate(ids):
            meta = dict(metas[idx] or {}) if idx < len(metas) else {}
            meta.pop("user_id", None)
            dist = float(dists[idx]) if idx < len(dists) else 1.0
            score = max(0.0, 1.0 - dist)
            results.append(
                VectorRecord(
                    id=str(rec_id),
                    user_id=user_id,
                    text=str(docs[idx]) if idx < len(docs) else "",
                    metadata=meta,
                    score=score,
                )
            )
        return results

    def delete(self, *, record_id: str) -> None:
        self._collection.delete(ids=[record_id])


class UnifiedVectorStore:
    """Facade selecting Qdrant, Chroma, or embedded cosine search with resilient fallback."""

    def __init__(self, primary: VectorBackend, fallback: VectorBackend | None = None) -> None:
        self._primary = primary
        self._fallback = fallback or InMemoryVectorStore()

    @property
    def active_backend(self) -> str:
        return self._primary.backend_name

    def upsert(self, *, record_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None:
        try:
            self._primary.upsert(record_id=record_id, user_id=user_id, text=text, metadata=metadata)
        except Exception:
            self._fallback.upsert(record_id=record_id, user_id=user_id, text=text, metadata=metadata)

    def search(
        self, *, user_id: str, query: str, limit: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorRecord]:
        try:
            return self._primary.search(user_id=user_id, query=query, limit=limit, filters=filters)
        except Exception:
            return self._fallback.search(user_id=user_id, query=query, limit=limit, filters=filters)

    def delete(self, *, record_id: str) -> None:
        try:
            self._primary.delete(record_id=record_id)
        except Exception:
            self._fallback.delete(record_id=record_id)


def build_vector_store(
    *,
    backend: str = "auto",
    qdrant_url: str = "",
    qdrant_api_key: str = "",
    chroma_persist_dir: str = "",
    chroma_host: str = "",
) -> UnifiedVectorStore:
    """Instantiate configured vector store with graceful embedded fallback."""
    chosen = backend.lower()
    if chosen == "qdrant" or (chosen == "auto" and qdrant_url):
        try:
            return UnifiedVectorStore(
                QdrantVectorStore(
                    url=qdrant_url or None,
                    api_key=qdrant_api_key or None,
                    in_memory=not bool(qdrant_url),
                )
            )
        except Exception:
            pass
    if chosen == "chroma" or (chosen == "auto" and (chroma_host or chroma_persist_dir)):
        try:
            return UnifiedVectorStore(
                ChromaVectorStore(
                    persist_dir=chroma_persist_dir or None,
                    host=chroma_host or None,
                    ephemeral=not bool(chroma_host or chroma_persist_dir),
                )
            )
        except Exception:
            pass
    if chosen == "auto":
        try:
            return UnifiedVectorStore(QdrantVectorStore(in_memory=True))
        except Exception:
            pass
    return UnifiedVectorStore(InMemoryVectorStore())
