#from functools import lru_cache
#
#from pydantic_settings import BaseSettings, SettingsConfigDict
#
#
#class Settings(BaseSettings):
#    model_config = SettingsConfigDict(
#        env_file=".env",
#        env_file_encoding="utf-8",
#        case_sensitive=False,
#        extra="ignore",
#    )
#
#    paypal_client_id: str = ""
#    paypal_client_secret: str = ""
#    paypal_webhook_id: str = ""
#    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
#
#    anthropic_api_key: str = ""
#    anthropic_model: str = "claude-sonnet-5-5"
#
#    database_url: str = "sqlite:///./safepayout.db"
#
#    app_env: str = "development"
#    log_level: str = "INFO"
#
#
#@lru_cache
#def get_settings() -> Settings:
#    return Settings()
