"""Backend-only Storage REST adapter. Never returns credentials or raw provider errors."""
from urllib.parse import quote
import httpx
import re


class PrivateStorage:
    def __init__(self, settings):
        self.settings = settings

    def _request(self, method, path, **kwargs):
        extra_headers = kwargs.pop("headers", {})
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.request(method, self.settings.supabase_url + '/storage/v1/' + path,
                                      headers={'Authorization': 'Bearer ' + self.settings.service_key,
                                               'apikey': self.settings.service_key, **extra_headers}, **kwargs)
            response.raise_for_status()
            return response

    def check_private(self):
        bucket = self._request('GET', 'bucket/' + quote(self.settings.bucket, safe='')).json()
        if bucket.get('public') is not False:
            raise RuntimeError('Storage bucket must be private')

    def path(self, object_path):
        if not re.fullmatch(r'[0-9a-f-]{36}/[0-9a-f-]{36}\.(pdf|docx)', object_path):
            raise ValueError('Invalid object path')
        return quote(self.settings.bucket, safe='') + '/' + quote(object_path, safe='/')

    def upload(self, object_path, data, content_type):
        self.check_private()
        self._request('POST', 'object/' + self.path(object_path), content=data,
                      # No upsert: random objects must never overwrite existing ones.
                      headers={'Content-Type': content_type, 'x-upsert': 'false'})

    def delete(self, object_path):
        self.path(object_path)  # Validate generated path before sending prefixes.
        # Supabase remove API: missing objects are an idempotent empty result.
        self._request('DELETE', 'object/' + quote(self.settings.bucket, safe=''),
                      json={'prefixes': [object_path]})

    def sign(self, object_path):
        self.check_private()
        result = self._request('POST', 'object/sign/' + self.path(object_path), json={'expiresIn': 60}).json()
        path = result['signedURL']
        if not path.startswith('/object/sign/') or path.startswith('//'):
            raise ValueError('Unexpected signed URL')
        return self.settings.supabase_url + '/storage/v1' + path
