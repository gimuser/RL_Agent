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
        # Origins allowed by the backend CORS policy (frontend dev servers)
        self.api_allowed_origins: list[str] = [
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]


settings = Settings()
