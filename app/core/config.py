import os

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

settings = Settings()