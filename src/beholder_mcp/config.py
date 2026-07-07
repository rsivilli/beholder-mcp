from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    beholder_api_key: str = ""
    beholder_base_url: str = "https://api.beholder-gov.com"

    @field_validator("beholder_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "BEHOLDER_API_KEY is not set. "
                "Get an API key at https://api.beholder-gov.com/docs"
            )
        return v


settings = Settings()
