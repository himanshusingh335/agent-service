from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "tasks.db"

    host: str = "0.0.0.0"
    port: int = 8010
    reload: bool = False


settings = Settings()
