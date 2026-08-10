"""Runtime settings for the backend.

This simple settings object avoids importing pydantic.BaseSettings which may
not be available in all test environments. Use environment variables or a
proper settings management package in production.
"""

class Settings:
    def __init__(self):
        self.app_name: str = "SOAR-RL-Agent"
        self.debug: bool = True
        self.api_host: str = "0.0.0.0"
        self.api_port: int = 8000
        self.mongo_uri: str = "mongodb://localhost:27017"
        self.database_name: str = "soar_rl_agent"
        self.mongo_timeout_ms: int = 1000


settings = Settings()
