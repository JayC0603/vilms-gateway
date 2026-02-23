from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    HOST_PLATFORM: Literal["dgpu", "js"]
    ENGINE: Literal["vllm", "ollama"]
    BASE_URL: str
    MODELS: str
    DEFAULT_MAX_FRAMES: int = 8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

