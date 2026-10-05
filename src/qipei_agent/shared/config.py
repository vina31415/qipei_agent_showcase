# plan-P1-1,P1-3
"""配置加载：pydantic-settings 环境变量 + config/*.yaml 业务默认值"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（qipei-agent/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def _load_yaml(name: str) -> dict:
    """加载 config/{name}.yaml"""
    path = CONFIG_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    """环境变量（必填，无默认值）+ 业务配置默认值"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 金蝶 ERP
    KINGDEE_BASE_URL: str = Field(..., description="金蝶 ERP 基础地址")
    KINGDEE_TOKEN: str = Field(..., description="金蝶初始 access_token")
    KINGDEE_REFRESH_TOKEN: str = Field(..., description="金蝶 refresh_token")

    # PIM
    PIM_BASE_URL: str = Field(..., description="PIM 基础地址")
    PIM_ACCESS_TOKEN: str = Field(..., description="PIM 初始 access_token")
    PIM_REFRESH_TOKEN: str = Field(..., description="PIM refresh_token")

    # 豆包 LLM
    DOUBAO_API_KEY: str = Field(..., description="豆包 API Key")
    DOUBAO_MODEL: str = Field(..., description="豆包模型名称")

    # MySQL
    MYSQL_HOST: str = Field(..., description="MySQL 主机")
    MYSQL_PORT: int = Field(..., description="MySQL 端口")
    MYSQL_USER: str = Field(..., description="MySQL 用户")
    MYSQL_PASSWORD: str = Field(..., description="MySQL 密码")
    MYSQL_DB: str = Field(..., description="MySQL 数据库名")

    # Redis
    REDIS_URL: str = Field(..., description="Redis 连接地址")

    # 业务配置默认值（从 config/app.yaml 加载）
    _app_config: Optional[dict] = None

    def model_post_init(self, __context) -> None:
        """加载 config/*.yaml 业务默认值"""
        self._app_config = _load_yaml("app")

    @property
    def app_config(self) -> dict:
        if self._app_config is None:
            self._app_config = _load_yaml("app")
        return self._app_config

    @property
    def oe_normalize_config(self) -> dict:
        return _load_yaml("oe_normalize")

    @property
    def brand_normalize_config(self) -> dict:
        return _load_yaml("brand_normalize")

    @property
    def customer_level_config(self) -> dict:
        return _load_yaml("customer_level")

    @property
    def permission_config(self) -> dict:
        return _load_yaml("permission")


# 全局单例（延迟初始化，避免 import 时环境变量未设置报错）
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """测试用：重置单例"""
    global _settings
    _settings = None
