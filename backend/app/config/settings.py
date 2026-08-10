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

        # API activity tracking: define components to track by prefix and
        # a timeout in seconds after which an API is considered 'down' if not
        # observed.
        self.enable_api_activity_tracking: bool = True
        self.api_status_poll_interval: int = 5  # seconds
        self.api_status_timeout_seconds: int = 15  # mark 'down' if not seen within this

        # Whether to persist API statuses to the database
        self.persist_api_statuses: bool = True

        # Components to track. Each component is identified by a name and a
        # request path prefix. Incoming requests that start with the prefix
        # update the component's last-seen timestamp and status.
        self.api_components: list[dict] = [
            {"name": "training", "prefix": "/api/training"},
            {"name": "database", "prefix": "/api/database"},
            {"name": "alerts", "prefix": "/api/alerts"},
            {"name": "decisions", "prefix": "/api/decisions"},
            {"name": "rewards", "prefix": "/api/rewards"},
            {"name": "dashboard", "prefix": "/api/dashboard"},
            {"name": "agent", "prefix": "/api/agent"},
            {"name": "evaluation", "prefix": "/api/evaluation"},
        ]


settings = Settings()
