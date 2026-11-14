"""Fail-closed optional cloud configuration."""
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class CloudSettings:
    supabase_url: str
    issuer: str
    audience: str
    jwks_url: str
    algorithm: str
    database_url: str = field(repr=False)
    bucket: str
    service_key: str = field(repr=False)

    def __post_init__(self):
        origin = urlsplit(self.supabase_url)
        if (origin.scheme != 'https' or not origin.hostname or origin.path
                or origin.query or origin.fragment or origin.username or origin.password):
            raise ValueError('SUPABASE_URL must be an HTTPS origin')
        if self.issuer != self.supabase_url + '/auth/v1':
            raise ValueError('JWT issuer must match the configured Supabase project')
        if self.jwks_url != self.issuer + '/.well-known/jwks.json':
            raise ValueError('JWKS must belong to the configured Supabase project')
        if self.algorithm not in {'ES256', 'RS256'} or not self.audience:
            raise ValueError('Explicit asymmetric algorithm and audience required')
        if not self.database_url.startswith('postgresql+psycopg://'):
            raise ValueError('CLOUD_DATABASE_URL must use postgresql+psycopg')
        if not self.bucket or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in self.bucket):
            raise ValueError('Invalid private bucket name')
        if not self.service_key.strip():
            raise ValueError('Backend storage credential required')

    @classmethod
    def from_env(cls):
        enabled = os.getenv('CLOUD_ENABLED', 'false')
        if enabled not in {'true', 'false'}:
            raise ValueError('CLOUD_ENABLED must be true or false')
        if enabled == 'false':
            return None
        names = ('SUPABASE_URL', 'SUPABASE_JWT_ISSUER', 'SUPABASE_JWT_AUDIENCE',
                 'SUPABASE_JWKS_URL', 'SUPABASE_JWT_ALGORITHM', 'CLOUD_DATABASE_URL',
                 'SUPABASE_STORAGE_BUCKET', 'SUPABASE_SERVICE_ROLE_KEY')
        return cls(*(os.environ[name] for name in names))
