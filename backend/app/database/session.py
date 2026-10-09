from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path

class Settings(BaseSettings):
    database_url: str

    mqtt_broker_host: str = "152.42.238.142"
    mqtt_broker_port: int = 1883
    mqtt_candidate_id: str = "11"
    mqtt_keepalive: int = 60

    model_config = SettingsConfigDict(
    env_file=Path(__file__).resolve().parents[2] / ".env",
    extra="ignore",
)


settings = Settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
