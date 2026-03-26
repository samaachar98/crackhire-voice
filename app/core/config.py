from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = ""
    minimax_api_key: str = ""
    groq_api_key: str = ""
    minimax_model: str = "MiniMax-M2.7"
    piper_voice_path: str = "/home/ubuntu/.openclaw/workspace/backend/data/piper_voices"
    piper_voice: str = "en_US-lessac-medium"
    host: str = "0.0.0.0"
    port: int = 7000
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
