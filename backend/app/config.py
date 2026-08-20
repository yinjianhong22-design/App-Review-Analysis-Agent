from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "App Review Analysis Agent"
    log_level: str = "info"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "deepseek-chat"
    openai_deep_model: str = "deepseek-chat"

    # Workflow settings
    max_reviews_per_app: int = 500
    rss_page_size: int = 50
    rss_max_pages: int = 10
    rss_request_delay_ms: int = 1200
    min_evidence_reviews: int = 3
    llm_temperature: float = 0.1
    llm_max_retries: int = 3
    # json_schema: OpenAI-style strict structured output (requires provider support)
    # json_object: broader compatibility; schema is appended to prompt (recommended for DeepSeek)
    # disabled: do not pass response_format at all (maximum compatibility)
    llm_json_mode: str = "json_object"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
