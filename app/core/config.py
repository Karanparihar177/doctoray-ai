from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Doctoray AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    # Speech-to-text (Deepgram). The key stays in .env and is never logged.
    deepgram_ai_key: SecretStr | None = None
    deepgram_base_url: str = "https://api.deepgram.com"
    deepgram_model: str = "nova-3"

    # Largest audio upload accepted by POST /transcriptions.
    max_upload_mb: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
