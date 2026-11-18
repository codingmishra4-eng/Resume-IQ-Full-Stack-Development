"""API-only configuration; importing Streamlit never imports this module."""

import math
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import config


@dataclass(frozen=True)
class APISettings:
    allowed_origins: tuple[str, ...] = ()
    max_upload_bytes: int = int(config.MAX_UPLOAD_BYTES)
    public_mode: bool = False
    legacy_upload_enabled: bool = True

    def __post_init__(self) -> None:
        if self.public_mode and self.legacy_upload_enabled:
            raise ValueError('Public mode requires API_LEGACY_UPLOAD_ENABLED=false.')
        if self.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_MB must be a positive finite size.")
        for origin in self.allowed_origins:
            try:
                url = urlsplit(origin)
                port = url.port
                valid = (
                    url.scheme in {"http", "https"} and bool(url.hostname)
                    and not url.username and not url.password
                    and not url.path and not url.query and not url.fragment
                    and "*" not in origin and not any(c.isspace() for c in origin)
                    and (port is None or 0 < port <= 65535)
                    and origin == f"{url.scheme}://{url.netloc}"
                )
            except ValueError:
                valid = False
            if self.public_mode and not origin.startswith("https://"):
                valid = False
            if not valid:
                raise ValueError("API_ALLOWED_ORIGINS must contain exact HTTP(S) origins without paths or wildcards.")

    @classmethod
    def from_env(cls) -> "APISettings":
        size_mb = float(os.getenv("MAX_UPLOAD_MB", "10"))
        if not math.isfinite(size_mb) or size_mb <= 0:
            raise ValueError("MAX_UPLOAD_MB must be a positive finite size.")
        origins = tuple(dict.fromkeys(
            value.strip() for value in os.getenv("API_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        ))
        def flag(name, default):
            value = os.getenv(name, default)
            if value not in {'true', 'false'}:
                raise ValueError(f'{name} must be true or false.')
            return value == 'true'
        return cls(allowed_origins=origins, max_upload_bytes=int(size_mb * 1024 * 1024),
                   public_mode=flag('API_PUBLIC_MODE', 'false'),
                   legacy_upload_enabled=flag('API_LEGACY_UPLOAD_ENABLED', 'true'))
