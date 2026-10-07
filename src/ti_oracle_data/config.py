from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    opendota_api_key: str | None
    request_delay_seconds: float
    request_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        configured_database = os.getenv("TI_ORACLE_DATABASE")
        return cls(
            database_path=(
                Path(configured_database).expanduser()
                if configured_database
                else PROJECT_ROOT / "data/ti_oracle.sqlite3"
            ),
            opendota_api_key=os.getenv("OPENDOTA_API_KEY") or None,
            request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "1.1")),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        )
