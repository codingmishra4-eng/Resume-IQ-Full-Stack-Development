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
from scripts.verify_phase2 import Verifier, require


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Phase5Verifier(Verifier):
    def __init__(self, *args, migration_audit_url=None):
        super().__init__(*args)
        self.migration_audit_url = migration_audit_url
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
        url = self.migration_audit_url or os.getenv('PHASE5_MIGRATION_AUDIT_DATABASE_URL')
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


def main(argv=None):
    """No implicit env access. Each network-capable mode is an explicit opt-in."""
    import argparse
    import logging
    from pathlib import Path
    from scripts.verify_phase2 import Settings, VerificationError
    from scripts.staging_preflight import load_target, StagingReadOnly, report_environment
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise VerificationError('Invalid command arguments.')
    parser = Parser(description='Staging-only verification; no migrations or deployments.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--read-only', action='store_true')
    mode.add_argument('--allow-live-writes', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--expected-project-ref')
    parser.add_argument('--expected-api-origin')
    parser.add_argument('--cleanup-journal', type=Path)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        args = parser.parse_args(argv)
        if not args.read_only and not args.allow_live_writes:
            print('PENDING: choose --read-only or explicitly approve --allow-live-writes. No settings or services accessed.')
            return 2
        require(not args.cleanup_journal, 'Phase 5 recovery requires manual operator review.')
        # USERPROFILE is used only to construct the requested default path. No
        # other inherited cloud, DB, API, provider or password value is consulted.
        path = args.env_file
        if path is None:
            profile = os.environ.get('USERPROFILE')
            require(bool(profile), 'Use an explicit staging configuration path on this platform.')
            path = Path(profile)/'ResumeIQ-Private'/'staging.env'
        target = load_target(path, args.expected_project_ref)
        print('PASS: independently pinned staging project, database routing and TLS configuration')
        if args.read_only:
            report_environment(target)
            StagingReadOnly(target).run()
            print('PENDING: deployed API/frontend checks, Auth sessions, private Storage behavior, two-user isolation and browser QA require separate verification.')
            print('PASS: read-only audit completed; no accounts, files, Storage or application rows written.')
            return 0
        # The independently selected API pin prevents a staging env file from
        # accidentally routing integration writes to the original application's API.
        from scripts.verify_phase2 import origin
        require(bool(args.expected_api_origin), 'Live testing requires an independent staging API origin pin.')
        origin(args.expected_api_origin, local=True)
        require(target.values.get('PHASE2_API_URL') == args.expected_api_origin, 'Staging API origin mismatch.')
        # Password prompting, sessions and cleanup are reachable only in this branch.
        settings = Settings.from_mapping(target.values)
        engine = create_engine(target.runtime_url, hide_parameters=True, pool_pre_ping=True, connect_args={'connect_timeout':5})
        try:
            import httpx
            from uuid import uuid4
            with httpx.Client(timeout=90, follow_redirects=False) as client:
                verifier = Phase5Verifier(settings, client, engine, Path('work')/('phase2-verification-'+uuid4().hex+'.json'),
                                          migration_audit_url=target.audit_url.render_as_string(hide_password=False))
                return verifier.run()
        finally:
            engine.dispose()
    except VerificationError as error:
        print('FAIL:', str(error))  # VerificationError labels contain no input values.
        return 1
    except (Exception, KeyboardInterrupt):
        print('FAIL: staging verification could not complete; sensitive configuration and diagnostics suppressed.')
        return 1
    finally:
        logging.disable(previous)


if __name__=='__main__':
    raise SystemExit(main())
