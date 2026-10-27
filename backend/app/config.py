from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vaultly:vaultly@localhost:5432/vaultly"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    verify_token_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:5173"
    cookie_secure: bool = False


settings = Settings()
