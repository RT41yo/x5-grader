from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    pg_user: str = "x5"
    pg_password: str = "x5pass"
    pg_host: str = "postgres"
    pg_port: int = 5432
    pg_db: str = "x5checker"

    # Langflow
    langflow_url: str = "http://langflow:7860"

    # Secret (например, для JWT или CSRF)
    secret_key: str = "super-secret"

    @property
    def database_url(self):
        return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
