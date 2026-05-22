from pydantic import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    google_places_api_key: str
    database_url: str = "sqlite:///./khojapi.db"
    max_results_per_source: int = 20
    request_delay_seconds: float = 1.5

    class Config:
        env_file = ".env"

settings = Settings()
