"""
Vector embedding generation for semantic search.

Uses OpenAI's text-embedding-3-small model to generate
1536-dimensional vectors for transcript similarity search.
"""

from openai import AsyncOpenAI

from app.config import get_settings


async def _get_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimensional embedding vector for text.

    Args:
        text: Text to embed (transcript or phrase).

    Returns:
        1536-dimensional float vector.
    """
    try:
        client = await _get_client()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding

    except Exception as e:
        print(f"Error generating embedding: {e}")
        return [0.0] * 1536


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors.
    """
    try:
        client = await _get_client()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
            encoding_format="float",
        )
        return [item.embedding for item in response.data]

    except Exception as e:
        print(f"Error generating batch embeddings: {e}")
        return [[0.0] * 1536] * len(texts)


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import numpy as np

    v1 = np.array(vec1)
    v2 = np.array(vec2)

    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))
