from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "文件编号系统"
    database_url: str = "sqlite:///./filecode-dev.db"
    session_secret: str = "development-only-change-me"
    session_max_age_seconds: int = 28_800
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"

    wecom_auth_mode: str = "mock"
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_corp_secret: str = ""
    wecom_admin_user_ids: str = ""

    ai_mode: str = "rules"
    ai_api_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""

    rule_file_path: Path = PROJECT_ROOT / "编号规则采集模板.yaml"
    abbreviation_file_path: Path = PROJECT_ROOT / "文件简号.xlsx"
    auto_create_tables: bool = True

    @field_validator("wecom_auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        if value not in {"mock", "live"}:
            raise ValueError("WECOM_AUTH_MODE 只能为 mock 或 live")
        return value

    @field_validator("ai_mode")
    @classmethod
    def validate_ai_mode(cls, value: str) -> str:
        if value not in {"rules", "openai_compatible"}:
            raise ValueError("AI_MODE 只能为 rules 或 openai_compatible")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def wecom_admin_user_id_set(self) -> set[str]:
        return {
            item.strip().casefold()
            for item in self.wecom_admin_user_ids.split(",")
            if item.strip()
        }

    @property
    def wecom_admin_user_id_list(self) -> list[str]:
        return [
            item.strip()
            for item in self.wecom_admin_user_ids.split(",")
            if item.strip()
        ]

    def validate_runtime_secrets(self) -> None:
        if self.is_production:
            if (
                self.session_secret == "development-only-change-me"
                or len(self.session_secret) < 32
            ):
                raise RuntimeError("生产环境必须配置至少 32 位的 SESSION_SECRET")
            if not self.cookie_secure:
                raise RuntimeError("生产环境必须启用 COOKIE_SECURE")
            if not self.frontend_url.startswith("https://"):
                raise RuntimeError("生产环境 FRONTEND_URL 必须使用 HTTPS")
            if not self.backend_public_url.startswith("https://"):
                raise RuntimeError("生产环境 BACKEND_PUBLIC_URL 必须使用 HTTPS")
        if self.wecom_auth_mode == "live":
            required = {
                "WECOM_CORP_ID": self.wecom_corp_id,
                "WECOM_AGENT_ID": self.wecom_agent_id,
                "WECOM_CORP_SECRET": self.wecom_corp_secret,
                "WECOM_ADMIN_USER_IDS": self.wecom_admin_user_ids,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(f"企业微信 live 模式缺少配置：{', '.join(missing)}")
        if self.ai_mode == "openai_compatible":
            required = {
                "AI_API_BASE_URL": self.ai_api_base_url,
                "AI_API_KEY": self.ai_api_key,
                "AI_MODEL": self.ai_model,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(f"AI openai_compatible 模式缺少配置：{', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
