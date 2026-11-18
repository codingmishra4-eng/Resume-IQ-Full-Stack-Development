"""Render production entry point; no migrations, reload or sensitive access logs."""
import os
import logging
import uvicorn


class EventOnlyFormatter(logging.Formatter):
    def format(self, record):
        phase = {'Application startup complete.':'startup-complete',
                 'Application shutdown complete.':'shutdown-complete',
                 'Shutting down':'shutdown-start'}.get(str(record.msg), 'server event')
        return f"{record.levelname} {record.name} {phase}"


def options():
    port = int(os.getenv('PORT', '8000'))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid server port')
    return dict(host='0.0.0.0', port=port, workers=1, access_log=False,
                proxy_headers=False, server_header=False, timeout_keep_alive=5,
                timeout_graceful_shutdown=100, limit_concurrency=24,
                backlog=64, log_config='deploy/uvicorn-log.json')


def main():
    # Fail closed rather than accidentally publishing the local legacy API.
    if os.getenv('API_PUBLIC_MODE') != 'true' or os.getenv('API_LEGACY_UPLOAD_ENABLED') != 'false' or os.getenv('CLOUD_ENABLED') != 'true':
        raise RuntimeError('Production requires cloud mode and public legacy-upload blocking')
    if (os.getenv('CLOUD_MIGRATION_DATABASE_URL') or os.getenv('PHASE5_MIGRATION_AUDIT_DATABASE_URL')):
        raise RuntimeError('Migration credentials must not be present in the API environment')
    from sqlalchemy.engine import make_url
    try:
        database = make_url(os.environ['CLOUD_DATABASE_URL'])
        encrypted = database.query.get('sslmode') in {'require','verify-ca','verify-full'}
    except Exception:
        raise RuntimeError('Invalid production database configuration') from None
    if not encrypted:
        raise RuntimeError('Production database requires explicit TLS')
    from backend.api import app
    uvicorn.run(app, **options())


if __name__ == '__main__':
    main()
