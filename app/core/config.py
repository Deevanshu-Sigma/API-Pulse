from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Fernet symmetric encryption key for stored API credentials.
    # Generate once with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Paste the result into your .env as ENCRYPTION_KEY=<value>
    ENCRYPTION_KEY: str = ""

    # Email (optional — leave blank to skip)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # Twilio SMS (optional — leave blank to skip)
    TWILIO_SID: str = ""
    TWILIO_TOKEN: str = ""
    TWILIO_PHONE: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
