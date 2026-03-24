import asyncio

from fastembed import TextEmbedding
from config import EMBEDDING_MODEL

_model = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    model = get_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]


def generate_embedding(text: str) -> list[float]:
    return generate_embeddings([text])[0]


async def async_generate_embedding(text: str) -> list[float]:
    return await asyncio.to_thread(generate_embedding, text)


async def async_generate_embeddings(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(generate_embeddings, texts)
