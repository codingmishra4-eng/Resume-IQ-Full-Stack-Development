"""Every resource query includes verified ownership, even with a bypass-RLS role."""
from copy import copy
from uuid import UUID
from sqlalchemy import create_engine, select, event, text
from sqlalchemy.orm import sessionmaker, Session
from backend.api_v1.errors import APIError
from backend.cloud.models import Resume, Analysis, SavedResume


class CloudSession(Session):
    """Cloud-only transaction identity; never affects local Streamlit sessions."""


@event.listens_for(CloudSession, 'after_begin')
def set_transaction_identity(session, transaction, connection):
    if connection.dialect.name == 'postgresql':
        # SET LOCAL semantics: identity is cleared on commit/rollback/pool return.
        # An unscoped runtime session receives an empty identity and sees no rows.
        owner = session.info.get('cloud_user_id')
        connection.execute(text("SELECT set_config('resumeiq.user_id', :owner, true)"),
                           {'owner': str(owner) if owner else ''})


class CloudDatabase:
    def __init__(self, url):
        # Always qualify ORM tables on PostgreSQL; a temp/search_path relation
        # cannot shadow cloud tables. SQLite unit/local behavior stays unchanged.
        options = {'schema_translate_map': {None: 'public'}} if url.startswith('postgresql') else {}
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True,
                                    execution_options=options)
        self.sessions = sessionmaker(self.engine, class_=CloudSession, expire_on_commit=False)

    def for_user(self, user_id):
        """Return a request-local facade; never mutate shared request identity."""
        owner = UUID(str(user_id))
        if getattr(self, '_user_id', owner) != owner:
            raise ValueError('Cannot rebind a scoped database to another user')
        scoped = copy(self)
        scoped._user_id = owner
        scoped.sessions = sessionmaker(self.engine, class_=CloudSession,
                                      expire_on_commit=False, info={'cloud_user_id': owner})
        return scoped

    def owned(self, session, model, user_id, resource_id):
        row = session.scalar(select(model).where(model.id == resource_id, model.user_id == user_id).with_for_update())
        if row is None:
            raise APIError('not_found', 'Resource not found.', 404)
        return row

    def list(self, model, user_id, offset=0):
        with self.for_user(user_id).sessions() as session:
            query = select(model).where(model.user_id == user_id)
            if model is Resume:
                query = query.where(Resume.state == 'ready')
            return list(session.scalars(query.order_by(model.created_at.desc(), model.id).offset(offset).limit(100)))

    def create(self, model, user_id, **values):
        with self.for_user(user_id).sessions.begin() as session:
            row = model(user_id=user_id, **values)
            session.add(row)
            session.flush()
            return row

    def update(self, model, user_id, resource_id, **values):
        fields = {SavedResume: {'data_json'}, Analysis: {'summary_json'}}
        if model not in fields:
            raise ValueError('Unsupported update model')
        allowed = fields[model]
        if not set(values) <= allowed:
            raise ValueError('Unsupported update')
        with self.for_user(user_id).sessions.begin() as session:
            row = self.owned(session, model, user_id, resource_id)
            for name, value in values.items():
                setattr(row, name, value)
            return row

    def delete(self, model, user_id, resource_id):
        if model is Resume:
            raise ValueError('Use storage-aware resume deletion')
        with self.for_user(user_id).sessions.begin() as session:
            session.delete(self.owned(session, model, user_id, resource_id))
