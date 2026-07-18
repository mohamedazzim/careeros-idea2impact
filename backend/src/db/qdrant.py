from qdrant_client import AsyncQdrantClient
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Qdrant Client connection with timeout configuration
qdrant_client = AsyncQdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
    timeout=60.0,
)

async def get_qdrant() -> AsyncQdrantClient:
    return qdrant_client

async def validate_qdrant_connection():
    try:
        collections = await qdrant_client.get_collections()
        logger.info(f"Qdrant connection successful. Available collections: {collections.collections}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant at {settings.QDRANT_URL}: {e}")
        raise
