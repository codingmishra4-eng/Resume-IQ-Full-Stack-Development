"""Manual interrupted-operation reconciliation. Run with API traffic stopped."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from backend.cloud.settings import CloudSettings
from backend.cloud.database import CloudDatabase
from backend.cloud.models import Resume
from backend.cloud.storage import PrivateStorage


def reconcile(db, storage):
    """Delete unfinished objects older than 24h; retain intent on any failure."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    completed = 0
    with db.sessions.begin() as session:
        rows = session.scalars(select(Resume).where(
            Resume.state.in_(['pending', 'deleting']), Resume.updated_at < cutoff
        ).with_for_update(skip_locked=True))
        for row in rows:
            storage.delete(row.object_path)
            session.delete(row)
            completed += 1
    return completed


if __name__ == '__main__':
    settings = CloudSettings.from_env()
    if settings is None:
        raise SystemExit('Enable cloud mode before reconciliation')
    db = CloudDatabase(settings.database_url)
    try:
        print('Reconciled operations:', reconcile(db, PrivateStorage(settings)))
    except Exception:
        # Do not print provider errors, credentials, paths or database statements.
        raise SystemExit('Reconciliation failed; intents retained for retry') from None
    finally:
        db.engine.dispose()
