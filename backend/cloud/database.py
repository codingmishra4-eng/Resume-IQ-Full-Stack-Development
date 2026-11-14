"""Every resource query includes verified ownership, even with a bypass-RLS role."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.api_v1.errors import APIError
from backend.cloud.models import Resume, Analysis, SavedResume


class CloudDatabase:
    def __init__(self, url):
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def owned(self, session, model, user_id, resource_id):
        row = session.scalar(select(model).where(model.id == resource_id, model.user_id == user_id).with_for_update())
        if row is None:
            raise APIError('not_found', 'Resource not found.', 404)
        return row

    def list(self, model, user_id, offset=0):
        with self.sessions() as session:
            query = select(model).where(model.user_id == user_id)
            if model is Resume:
                query = query.where(Resume.state == 'ready')
            return list(session.scalars(query.order_by(model.created_at.desc(), model.id).offset(offset).limit(100)))

    def create(self, model, user_id, **values):
        with self.sessions.begin() as session:
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
        with self.sessions.begin() as session:
            row = self.owned(session, model, user_id, resource_id)
            for name, value in values.items():
                setattr(row, name, value)
            return row

    def delete(self, model, user_id, resource_id):
        if model is Resume:
            raise ValueError('Use storage-aware resume deletion')
        with self.sessions.begin() as session:
            session.delete(self.owned(session, model, user_id, resource_id))
