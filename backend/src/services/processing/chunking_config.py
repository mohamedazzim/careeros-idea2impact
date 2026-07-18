from pydantic_settings import BaseSettings

class ChunkingConfig(BaseSettings):
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200

    class Config:
        env_prefix = "CHUNKING_"

chunking_config = ChunkingConfig()
