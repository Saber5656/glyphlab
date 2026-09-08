"""Environment configuration; sensitive values never appear in dumps or repr."""

import re
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHLAB_")
    data_dir: Path = Path("/data")
    database_url: str = ""
    object_store: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    retention_days: float = Field(default=14.0, gt=0)
    public_base_url: str = ""
    environment: Literal["dev", "prod"] = "prod"
    trust_proxy_headers: bool = False
    cors_dev_origin: str = "http://localhost:5173"
    max_upload_bytes: int = Field(default=12 * 2**20, gt=0)
    max_upload_request_bytes: int = Field(default=13 * 2**20, gt=0)
    max_json_body_bytes: int = Field(default=65536, gt=0)
    max_uploads_per_project: int = Field(default=40, gt=0)
    max_project_storage_bytes: int = Field(default=100 * 2**20, gt=0)
    max_queued_jobs_per_project: int = Field(default=5, gt=0)
    max_store_bytes: int = Field(default=5 * 2**30, gt=0)
    job_concurrency: int = Field(default=1, gt=0, le=16)
    job_timeout_s: int = Field(default=150, gt=0)
    sweep_interval_s: int = Field(default=3600, gt=0)
    rl_create_per_minute: int = Field(default=3, gt=0)
    rl_create_per_day: int = Field(default=10, gt=0)
    rl_uploads_per_hour_ip: int = Field(default=40, gt=0)
    rl_uploads_per_hour_project: int = Field(default=20, gt=0)
    rl_builds_per_hour_project: int = Field(default=10, gt=0)
    rl_default_per_minute: int = Field(default=120, gt=0)
    webui_dist: Path = Path("/app/webui-dist")

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'glyphlab.db'}"

    def model_dump(self, **kwargs):
        result = super().model_dump(**kwargs)
        return {
            k: "[masked]"
            if re.search(r"secret|key|password", k, re.IGNORECASE) or k == "database_url"
            else v
            for k, v in result.items()
        }

    def __repr_args__(self):
        return list(self.model_dump().items())
