"""Opt-in Phase 4 staging checks, reusing the Phase 2 synthetic cleanup journal.

No migration is applied. A separate operator-only connection reads the revision in
READ ONLY mode. Never deploy that connection in the API environment.
"""
import hashlib
import json
import os
import time
from uuid import UUID
from sqlalchemy import create_engine, text
from scripts.verify_phase2 import Verifier, require, main


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Phase5Verifier(Verifier):
    def __init__(self, *args):
        super().__init__(*args)
        self.draft_baseline, self.drafts, self.feature_ids = {}, {}, {}
        self.draft_data = {'template':'essential','draft':{'name':'Synthetic Verification Candidate',
            'title':'Engineer','email':'','phone':'','location':'','summary':'Synthetic Python SQL testing.',
            'experience':'Built synthetic testing software.','education':'','skills':'Python, SQL'}}
        self.draft_hash = digest(self.draft_data)
        self.ambiguous_draft = False

    def api(self, method, path, user=None, **kwargs):
        response = super().api(method,path,user,**kwargs)
        # Only the known pre-operation quota rejection may be retried. Never
        # replay a timeout, network error, 5xx, generic 429 or uncertain write.
        if response.status_code == 429:
            try:
                delay = int(response.headers.get('Retry-After','0'))
                rejected = response.json().get('code') == 'rate_limited'
            except Exception:
                rejected, delay = False, 0
            if rejected and 1 <= delay <= 60:
                time.sleep(delay)
                return super().api(method,path,user,**kwargs)
        return response

    def audit_database(self):
        super().audit_database()
        url = os.getenv('PHASE5_MIGRATION_AUDIT_DATABASE_URL')
        require(url and url.startswith('postgresql+psycopg://'), 'Operator-only read-only migration audit connection is required.')
        audit = create_engine(url, hide_parameters=True, connect_args={'connect_timeout':5}, pool_pre_ping=True)
        try:
            with audit.begin() as connection:
                connection.execute(text('SET TRANSACTION READ ONLY'))
                revisions = connection.scalars(text('SELECT version_num FROM public.alembic_version')).all()
                require(revisions == ['0002_feature_links'], 'Expected migration 0002_feature_links before feature tests.')
        finally:
            audit.dispose()
        with self.engine.connect() as connection:
            require(connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conrelid='public.cloud_analyses'::regclass AND conname='fk_cloud_analysis_resume_owner'")) == 1, 'Runtime database lacks the feature ownership constraint.')

    def draft_rows(self, user):
        with self.engine.begin() as connection:
            connection.execute(text("SELECT set_config('resumeiq.user_id', :owner, true)"), {'owner':user['id']})
            return list(connection.execute(text('SELECT id,data_json FROM public.cloud_saved_resumes WHERE user_id=:owner'), {'owner':UUID(user['id'])}).mappings())

    def login(self):
        super().login()
        for user in self.users:
            owner = user['id']
            self.draft_baseline[owner] = {str(row['id']) for row in self.draft_rows(user)}
            self.drafts[owner] = set()
            self.feature_ids[owner] = set()
        self.save_journal()

    def journal_data(self):
        data = super().journal_data()
        data['phase5'] = {'baseline':{owner:sorted(ids) for owner,ids in self.draft_baseline.items()},
            'drafts':{owner:sorted(ids) for owner,ids in self.drafts.items()},'draft_hash':self.draft_hash,
            'feature_ids':{owner:sorted(ids) for owner,ids in self.feature_ids.items()},'ambiguous':self.ambiguous_draft}
        return data

    def lifecycle(self):
        super().lifecycle()
        self.active = 'Phase 4 synthetic feature lifecycle'
        jd = 'Python SQL Docker engineer working on testing systems and software delivery with real projects.'
        for user in self.users:
            other = next(item for item in self.users if item is not user)
            id = next(iter(self.created[user['id']]))
            for route, payload, field in [('analyses',{},'report'),('matches',{'job_description':jd},'result')]:
                response = self.api('POST',f'/api/v1/resumes/{id}/{route}',user,json=payload)
                require(response.status_code==201,'Feature computation failed.')
                data = response.json(); resource = str(UUID(data['id']))
                self.feature_ids[user['id']].add(resource);self.save_journal()
                require(data['resume_id']==id and field in data,'Feature response is not linked to owned resume.')
                target = '/api/v1/'+('analysis-reports/' if route=='analyses' else 'job-matches/')+resource
                require(self.api('GET',target,user).status_code==200,'Saved feature retrieval failed.')
                require(self.api('GET',target,other).status_code==404,'Cross-user report access accepted.')
                require(self.api('POST',f'/api/v1/resumes/{id}/{route}',other,json=payload).status_code==404,'Cross-user computation accepted.')
            response=self.api('POST',f'/api/v1/resumes/{id}/improvements',user,json={'kind':'keywords','job_description':jd,'use_ai':False})
            require(response.status_code==200 and response.json()['provider_used'] is False,'Rule-only improvement failed.')
            require(self.api('POST',f'/api/v1/resumes/{id}/improvements',other,json={'kind':'summary'}).status_code==404,'Cross-user improvement accepted.')
            self.ambiguous_draft=True;self.save_journal()
            response=self.api('POST','/api/v1/builder/drafts',user,json=self.draft_data)
            require(response.status_code==201,'Synthetic draft save failed.')
            draft=str(UUID(response.json()['id']))
            require(draft not in self.draft_baseline[user['id']],'Draft overlaps existing data.')
            self.drafts[user['id']].add(draft);self.ambiguous_draft=False;self.save_journal()
            path=f'/api/v1/builder/drafts/{draft}'
            require(self.api('GET',path,user).status_code==200,'Draft retrieval failed.')
            require(self.api('PUT',path,user,json=self.draft_data).status_code==200,'Draft update failed.')
            for method in ('GET','PUT','DELETE'):
                kwargs={'json':self.draft_data} if method=='PUT' else {}
                require(self.api(method,path,other,**kwargs).status_code==404,'Cross-user draft access accepted.')
            for fmt in ('pdf','docx'):
                response=self.api('POST',path+'/exports/'+fmt,user)
                require(response.status_code==200 and response.content.startswith(b'%PDF' if fmt=='pdf' else b'PK'),'Synthetic export failed.')
                require(response.headers.get('cache-control')=='private, no-store','Export caching is unsafe.')
                require(self.api('POST',path+'/exports/'+fmt,other).status_code==404,'Cross-user export accepted.')
        self.passed+=1
        print('PASS: owned analysis, matching, rule-only improvements and builder exports')

    def cleanup(self):
        ok=not self.ambiguous_draft
        # Recover ambiguous draft writes by content hash, never by age/name alone.
        for user in self.users:
            owner=user['id']
            if owner not in self.draft_baseline: continue
            try:
                for row in self.draft_rows(user):
                    id=str(row['id'])
                    if id in self.draft_baseline[owner]: continue
                    if digest(row['data_json'])==self.draft_hash:
                        self.drafts[owner].add(id)
                    elif id not in self.drafts[owner]:
                        ok=False
                self.save_journal()
                for id in self.drafts[owner]:
                    response=self.api('DELETE',f'/api/v1/builder/drafts/{id}',user)
                    require(response.status_code in {204,404},'Draft cleanup failed.')
                    require(id not in {str(row['id']) for row in self.draft_rows(user)},'Draft content remained.')
                with self.engine.begin() as connection:
                    connection.execute(text("SELECT set_config('resumeiq.user_id',:owner,true)"),{'owner':owner})
                    # Discover lost report responses through the same-owner FK.
                    for id in self.created.get(owner,set()):
                        self.feature_ids.setdefault(owner,set()).update(str(value) for value in connection.scalars(text('SELECT id FROM public.cloud_analyses WHERE user_id=:owner AND resume_id=:id'),{'owner':UUID(owner),'id':UUID(id)}))
                    for id in self.drafts[owner] | self.feature_ids.get(owner,set()):
                        connection.execute(text('DELETE FROM public.cloud_history WHERE user_id=:owner AND resource_id=:id'),{'owner':UUID(owner),'id':UUID(id)})
            except Exception:
                ok=False
        if not ok:
            # Base must retain its recovery journal even if original cleanup works.
            self.ambiguous_upload=True
        return super().cleanup() and ok

    def recover(self, source):
        # A Phase 5 journal needs operator review on process interruption: base
        # recovery alone cannot prove draft/report ownership from a stale UUID.
        self.failed+=1
        print('FAIL: Phase 5 recovery requires operator review; retained journal unchanged. Do not use the Phase 2 recovery command for this journal.')
        return 1


if __name__=='__main__':
    raise SystemExit(main(verifier_class=Phase5Verifier, request_timeout=90))
