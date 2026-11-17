"""Only verified Supabase access tokens establish identity."""
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Request
from backend.api_v1.errors import APIError


@dataclass(frozen=True)
class Identity:
    id: UUID


class TokenVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.keys = jwt.PyJWKClient(settings.jwks_url, timeout=5, lifespan=300)

    def verify(self, token: str) -> Identity:
        header = jwt.get_unverified_header(token)
        if header.get('alg') != self.settings.algorithm or not isinstance(header.get('kid'), str):
            raise ValueError('Invalid signing header')
        key = self.keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=[self.settings.algorithm],
                            issuer=self.settings.issuer, audience=self.settings.audience,
                            options={'require': ['sub', 'iss', 'aud', 'exp', 'iat']})
        if claims.get('role') != 'authenticated':
            raise ValueError('Not a user access token')
        return Identity(UUID(claims['sub']))


def current_user(request: Request) -> Identity:
    value = request.headers.get('authorization', '')
    parts = value.split()
    verifier = request.app.state.token_verifier
    if len(parts) == 2 and parts[0].lower() == 'bearer' and len(parts[1]) <= 16384 and verifier:
        try:
            return verifier.verify(parts[1])
        except Exception:
            pass  # No token, key-fetch error, or claim details cross the API boundary.
    error = APIError('unauthorized', 'Authentication required.', 401)
    error.headers = {'WWW-Authenticate': 'Bearer'}
    raise error
