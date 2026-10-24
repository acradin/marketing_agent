from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VE_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/viral.db"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_json_mode: bool = True
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    reddit_token: str = ""
    reddit_user_agent: str = "viral-engine/0.1"
    youtube_api_key: str = ""
    allow_public_urls: bool = False
    enable_publishing: bool = False
    reddit_subreddit: str = ""
    x_bearer_token: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_user_id: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    x_redirect_uri: str = "http://127.0.0.1:8765/api/connections/x/callback"
    x_oauth_token: str = ""
    x_refresh_token: str = ""
    x_token_expires_at: float = 0
    instagram_app_id: str = Field(default="", validation_alias=AliasChoices("VE_INSTAGRAM_APP_ID", "INSTAGRAM_APP_ID"))
    instagram_app_secret: str = Field(default="", validation_alias=AliasChoices("VE_INSTAGRAM_APP_SECRET", "INSTAGRAM_APP_SECRET"))
    instagram_redirect_uri: str = "https://localhost/instagram/callback"
    instagram_auth_mode: str = "facebook"
    instagram_token: str = ""
    instagram_user_id: str = ""
    instagram_api_version: str = "v24.0"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_model.strip() and self.llm_api_key.strip())
