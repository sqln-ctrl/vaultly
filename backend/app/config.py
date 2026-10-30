from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite is the default for local development. Set DATABASE_URL to a
    # PostgreSQL/Supabase connection string when deploying.
    database_url: str = "sqlite:///./vaultly.db"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    verify_token_minutes: int = 60 * 24
    reset_token_minutes: int = 30
    frontend_url: str = "http://localhost:5173"
    cookie_secure: bool = False
    storage_dir: str = "./data/documents"
    app_env: str = "development"
    resend_api_key: str | None = None
    email_from: str = "Vaultly <onboarding@resend.dev>"


settings = Settings()
