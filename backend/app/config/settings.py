from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SOAR-RL-Agent"
    debug: bool = True


settings = Settings()
