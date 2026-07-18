import httpx
import logging
from typing import List
from langsmith import traceable

from src.core.config import settings

logger = logging.getLogger(__name__)


class NVEmbedV1Service:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.NVIDIA_API_KEY or ""
        self.base_url = base_url or "https://integrate.api.nvidia.com/v1"
        self.model_name = "nvidia/nv-embed-v1"
        self.dimensions = 4096

    @traceable(name="generate_embeddings_nvembed")
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key:
            logger.warning("NVIDIA_API_KEY not set — falling back to mock embeddings")
            return self._mock_generate(texts)

        # Real NVIDIA HTTP call
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": texts,
            "model": self.model_name,
            "input_type": "passage",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                embeddings = []
                # ensure returned in order
                sorted_data = sorted(data.get("data", []), key=lambda x: x["index"])
                for item in sorted_data:
                    embeddings.append(item["embedding"])
                    
                return embeddings
        except Exception as e:
            logger.error(f"NV-Embed-v1 API error: {e}")
            logger.warning("Falling back to mock embeddings")
            return self._mock_generate(texts)

    @traceable(name="embed_query_nvembed")
    async def embed_query(self, text: str) -> List[float]:
        if not text:
            return []

        if not self.api_key:
            logger.warning("NVIDIA_API_KEY not set — falling back to mock embedding")
            return self._mock_generate([text])[0]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": [text],
            "model": self.model_name,
            "input_type": "query",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])[0]["embedding"]
        except Exception as e:
            logger.error(f"NV-Embed-v1 Query error: {e}")
            logger.warning("Falling back to mock embedding for query")
            return self._mock_generate([text])[0]

    def _mock_generate(self, texts: List[str]) -> List[List[float]]:
        # Mock 4096 dim vector
        # Return a normalized vector simulating dense embedding
        import math
        embeddings = []
        for i, text in enumerate(texts):
            # A completely rudimentary pseudo-random generation to fake 4096 dimensions
            vec = [(float(i + j) % 10.0) / 10.0 for j in range(self.dimensions)]
            # normalize
            norm = math.sqrt(sum(v*v for v in vec))
            if norm > 0:
                vec = [v/norm for v in vec]
            embeddings.append(vec)
        return embeddings

_nvembed_service = None


def get_nvembed_service() -> NVEmbedV1Service:
    """Lazily initialize and return the module-level singleton.

    Uses module-level lazy initialization to prevent import-time side effects
    and eliminate __init__.py re-export aliasing that breaks patch()/mock resolution.
    """
    global _nvembed_service
    if _nvembed_service is None:
        _nvembed_service = NVEmbedV1Service()
    return _nvembed_service


def reset_nvembed_service() -> None:
    """Reset singleton for testing. Forces reinitialization on next access."""
    global _nvembed_service
    _nvembed_service = None


def __getattr__(name: str):
    if name == "nvembed_service":
        return get_nvembed_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
