from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "SOAR-RL-Agent"
    debug: bool = True
    
    # Mongo Configuration
    mongo_uri: str = "mongodb://localhost:27017"
    database_name: str = "soar_db"
    
    # API Host/Port Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()