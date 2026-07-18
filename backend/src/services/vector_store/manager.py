import logging
from qdrant_client.models import Distance, VectorParams
from src.db.qdrant import get_qdrant
from langsmith import traceable

logger = logging.getLogger(__name__)

COLLECTIONS = [
    "careeros_resumes",
    "careeros_jobs",
    "careeros_knowledge"
]
DIMENSIONS = 4096

class VectorStoreManager:
    @traceable(name="manage_qdrant_collections")
    async def init_collections(self):
        """Initializes all required collections if they don't exist."""
        for col in COLLECTIONS:
            await self.create_collection(col)
                
    @traceable(name="create_collection")
    async def create_collection(self, collection_name: str):
        """Creates a vector collection safely, avoiding duplicates."""
        if collection_name not in COLLECTIONS:
            logger.warning(f"Collection {collection_name} is not in the allowed list.")
            
        exists = await self.collection_exists(collection_name)
        if not exists:
            qdrant = await get_qdrant()
            logger.info(f"Creating collection {collection_name} with dim {DIMENSIONS}")
            await qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=DIMENSIONS, distance=Distance.COSINE)
            )

    @traceable(name="collection_exists")
    async def collection_exists(self, collection_name: str) -> bool:
        qdrant = await get_qdrant()
        try:
            existing_col = await qdrant.get_collections()
            return collection_name in [c.name for c in existing_col.collections]
        except Exception as e:
            logger.error(f"Error checking if collection exists: {e}")
            return False

    @traceable(name="get_collection")
    async def get_collection(self, collection_name: str):
        qdrant = await get_qdrant()
        try:
            return await qdrant.get_collection(collection_name)
        except Exception as e:
            logger.error(f"Error fetching collection {collection_name}: {e}")
            return None

    @traceable(name="delete_collections")
    async def delete_collections(self):
        for col in COLLECTIONS:
            await self.delete_collection(col)

    @traceable(name="delete_collection")
    async def delete_collection(self, collection_name: str):
        qdrant = await get_qdrant()
        try:
            if await self.collection_exists(collection_name):
                logger.warning(f"Deleting collection {collection_name}")
                await qdrant.delete_collection(collection_name=collection_name)
        except Exception as e:
            logger.error(f"Failed deleting Qdrant Collection {collection_name}: {e}")

    @traceable(name="recreate_collection")
    async def recreate_collection(self, collection_name: str):
        await self.delete_collection(collection_name)
        await self.create_collection(collection_name)

_vector_store_manager = None


def get_vector_store_manager() -> VectorStoreManager:
    global _vector_store_manager
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    return _vector_store_manager


def reset_vector_store_manager() -> None:
    global _vector_store_manager
    _vector_store_manager = None


def __getattr__(name: str):
    if name == "vector_store_manager":
        return get_vector_store_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
