"""Deterministic engines and mocked private Storage. No cloud/AI credentials."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
import pymupdf
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.api import create_app
from backend.api_v1.settings import APISettings
from backend.cloud.auth import Identity, current_user
from backend.cloud.database import CloudDatabase
from backend.cloud.models import Base, Resume, Analysis, SavedResume
from backend.cloud import feature_engine
from backend.cloud.features import feature_slot

JD = 'Role: Python developer. Python SQL and Docker are required. Build testing systems with SQL and Docker using Python testing. Collaborate on testing and delivery.'
DATA = {'template':'essential','draft':{'name':'Synthetic Candidate','title':'Engineer','email':'test@example.invalid',
        'summary':'Python engineer building real software.', 'experience':'Built <b>safe</b> software & testing for real projects.',
        'education':'Computer science', 'skills':'Python, SQL'}}


class Storage:
    def __init__(self): self.objects = {}
    def upload(self, path, data, content_type): self.objects[path] = data
    def read(self, path, max_bytes):
        data = self.objects[path]
        assert len(data) <= max_bytes
        return data
    def delete(self, path): self.objects.pop(path, None)
    def sign(self, path): return 'https://example.invalid/temporary'


@pytest.fixture
def feature_cloud():
    app = create_app(APISettings())
    owner = Identity(uuid4())
    app.dependency_overrides[current_user] = lambda: owner
    db = CloudDatabase.__new__(CloudDatabase)
    db.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    with db.engine.connect() as connection: connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(db.engine)
    db.sessions = sessionmaker(db.engine, expire_on_commit=False)
    storage = Storage()
    app.state.cloud_db, app.state.private_storage = db, storage
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app, owner, db, storage
    db.engine.dispose()


def upload(client, data):
    result = client.post('/api/v1/resumes', files={'file':('synthetic.pdf',data)})
    assert result.status_code == 201, result.text
    return result.json()['id']


def test_analysis_actual_results_privacy_and_history(feature_cloud, pdf_bytes):
    client, app, user, db, storage = feature_cloud
    id = upload(client, pdf_bytes)
    first = client.post(f'/api/v1/resumes/{id}/analyses', json={'job_description':JD})
    assert first.status_code == 201, first.text
    report = first.json()['report']
    assert set(report['ats']['categories']) == {'readability','structure','completeness','keywords','formatting','contact'}
    assert 0 <= report['ats']['overall'] <= 100
    assert report['contact']['email'] and 'private@example.invalid' not in first.text
    assert report['sections'] == ['skills']
    assert report['job_match']['matching']
    second = client.post(f'/api/v1/resumes/{id}/analyses', json={'job_description':JD})
    assert second.json()['report'] == report
    assert client.get('/api/v1/analyses').json()[0]['ats_score'] == report['ats']['overall']
    listed = client.get(f'/api/v1/resumes/{id}/analyses').json()
    assert len(listed) == 2 and 'report' not in listed[0]
    assert client.get('/api/v1/analysis-reports/' + first.json()['id']).status_code == 200
    assert 'analysis_created' in [item['event'] for item in client.get('/api/v1/history').json()]
    with db.sessions() as session:
        stored = session.scalar(select(Analysis))
        assert 'resume_text' not in stored.summary_json and JD not in json.dumps(stored.summary_json)
    assert client.delete(f'/api/v1/resumes/{id}').status_code == 204
    assert client.get('/api/v1/analysis-reports/' + first.json()['id']).status_code == 404


def test_matching_deterministic_and_not_counted_as_analysis(feature_cloud, pdf_bytes):
    client, _, _, _, _ = feature_cloud
    id = upload(client, pdf_bytes)
    a = client.post(f'/api/v1/resumes/{id}/matches', json={'job_description':JD})
    b = client.post(f'/api/v1/resumes/{id}/matches', json={'job_description':JD})
    assert a.status_code == 201, a.text
    assert a.json()['result'] == b.json()['result']
    assert 'python' in [value.lower() for value in a.json()['result']['matching']]
    assert 'docker' not in [value.lower() for value in a.json()['result']['matching']]
    assert client.get('/api/v1/analyses').json() == []
    assert client.get('/api/v1/job-matches/' + a.json()['id']).status_code == 200
    assert client.get('/api/v1/analyses/' + a.json()['id']).status_code == 404


def test_cross_user_all_feature_resources(feature_cloud, pdf_bytes):
    client, app, owner, db, storage = feature_cloud
    id = upload(client, pdf_bytes)
    report = client.post(f'/api/v1/resumes/{id}/analyses', json={}).json()['id']
    match = client.post(f'/api/v1/resumes/{id}/matches', json={'job_description':JD}).json()['id']
    draft = client.post('/api/v1/builder/drafts', json=DATA).json()['id']
    app.dependency_overrides[current_user] = lambda: Identity(uuid4())
    for method, path, body in [('POST',f'/resumes/{id}/analyses',{}),('POST',f'/resumes/{id}/matches',{'job_description':JD}),
        ('POST',f'/resumes/{id}/improvements',{'kind':'summary'}),('GET',f'/resumes/{id}/analyses',None),
        ('GET',f'/analysis-reports/{report}',None),('GET',f'/job-matches/{match}',None),
        ('GET',f'/builder/drafts/{draft}',None),('PUT',f'/builder/drafts/{draft}',DATA),
        ('DELETE',f'/builder/drafts/{draft}',None),('POST',f'/builder/drafts/{draft}/exports/pdf',None)]:
        result = client.request(method,'/api/v1'+path, json=body) if body is not None else client.request(method,'/api/v1'+path)
        assert result.status_code == 404, (path,result.text)
    assert client.get('/api/v1/builder/drafts').json() == []


def test_builder_crud_export_and_sanitization(feature_cloud, caplog):
    client, _, _, _, _ = feature_cloud
    templates = client.get('/api/v1/builder/templates').json()
    assert {item['id'] for item in templates} == {'essential','editorial','compact'}
    result = client.post('/api/v1/builder/drafts', json=DATA)
    assert result.status_code == 201, result.text
    id = result.json()['id']
    listed = client.get('/api/v1/builder/drafts').json()
    assert len(listed) == 1 and 'draft' not in listed[0] and 'Synthetic Candidate' not in json.dumps(listed)
    changed = {**DATA,'template':'editorial'}
    assert client.put(f'/api/v1/builder/drafts/{id}',json=changed).json()['template'] == 'editorial'
    pdf = client.post(f'/api/v1/builder/drafts/{id}/exports/pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert pdf.headers['cache-control'] == 'private, no-store'
    with pymupdf.open(stream=pdf.content, filetype='pdf') as document:
        assert 'Synthetic Candidate' in ''.join(page.get_text() for page in document)
    docx = client.post(f'/api/v1/builder/drafts/{id}/exports/docx')
    assert docx.status_code == 200
    doc = Document(BytesIO(docx.content))
    assert 'Built <b>safe</b> software & testing' in '\n'.join(item.text for item in doc.paragraphs)
    assert not doc.tables
    assert 'Synthetic Candidate' not in caplog.text
    assert client.delete(f'/api/v1/builder/drafts/{id}').status_code == 204
    assert client.post(f'/api/v1/builder/drafts/{id}/exports/pdf').status_code == 404


@pytest.mark.parametrize('changes', [{'template':'../../etc/passwd'}, {'user_id':str(uuid4())},
    {'draft':{'name':'  '}}, {'draft':{'name':'x','summary':'bad\x00text'}}, {'draft':{'name':'x','email':'invalid'}}],
    ids=['path-template','owner-injection','blank-name','xml-control','invalid-email'])
def test_invalid_drafts(feature_cloud, changes):
    client = feature_cloud[0]
    assert client.post('/api/v1/builder/drafts', json=DATA | changes).status_code == 422


def test_size_limits_invalid_inputs_and_ai_grounding(feature_cloud, pdf_bytes):
    client = feature_cloud[0]; id = upload(client,pdf_bytes)
    assert client.post(f'/api/v1/resumes/{id}/matches',json={'job_description':'short'}).status_code == 422
    assert client.post(f'/api/v1/resumes/{id}/improvements',json={'kind':'summary','text':'Invented employer and role'}).status_code == 400
    assert client.post(f'/api/v1/resumes/{id}/improvements',json={'kind':'summary','text':'Python SQL testing development teamwork delivery','use_ai':True}).status_code == 200
    assert client.put('/api/v1/builder/drafts/'+str(uuid4()), content=b'{"x":"'+b'x'*140000+b'"}', headers={'Content-Type':'application/json'}).status_code == 413


def test_ai_failure_and_invention_fall_back_without_new_facts(monkeypatch):
    parsed = SimpleNamespace(text='Summary\nWorked on Python testing and reduced errors 20%.', sections={'summary':'Worked on Python testing and reduced errors 20%.'})
    request = SimpleNamespace(kind='summary',text=parsed.sections['summary'],use_ai=True,job_description=None)
    fake = SimpleNamespace(ai_available=True, rewrite_summary=lambda *args: SimpleNamespace(original=request.text, improved='Led Google teams and increased revenue 300%.', source='openai'))
    monkeypatch.setattr(feature_engine,'make_assistant',lambda enabled:fake)
    result = feature_engine.improve_resume(parsed,request,True)
    assert result[0].source == 'rule-based' and 'Google' not in result[0].improved and '300' not in result[0].improved
    fake.rewrite_summary = lambda *args: (_ for _ in ()).throw(RuntimeError('sensitive-provider-error'))
    assert feature_engine.improve_resume(parsed,request,True)[0].source == 'rule-based'


def test_concurrency_slot_cleanup():
    owner = Identity(uuid4()); first = feature_slot(owner); next(first)
    with pytest.raises(Exception) as exc: next(feature_slot(owner))
    assert exc.value.status_code == 429
    first.close()
    second = feature_slot(owner); next(second); second.close()


def test_failed_generation_cleans_temporary_files(monkeypatch):
    paths = []
    def fail(self, resume, template, path):
        paths.append(path); path.write_bytes(b'partial'); raise RuntimeError('render failure')
    monkeypatch.setattr(feature_engine.ResumePDFGenerator,'generate',fail)
    from backend.cloud.feature_schemas import DraftInput
    with pytest.raises(RuntimeError): feature_engine.export_draft(DraftInput.model_validate(DATA),'pdf')
    assert paths and not paths[0].parent.exists()


@pytest.mark.parametrize('method,path,payload', [
    ('POST','/resumes/{id}/analyses',{}), ('GET','/resumes/{id}/analyses',None),
    ('POST','/resumes/{id}/matches',{'job_description':JD}), ('GET','/job-matches/{id}',None),
    ('GET','/analysis-reports/{id}',None),('POST','/resumes/{id}/improvements',{'kind':'summary'}),
    ('GET','/builder/templates',None),('GET','/builder/drafts',None),('POST','/builder/drafts',DATA),
    ('GET','/builder/drafts/{id}',None),('PUT','/builder/drafts/{id}',DATA),
    ('DELETE','/builder/drafts/{id}',None),('POST','/builder/drafts/{id}/exports/docx',None)],
    ids=['analyze','reports','match','saved-match','report','improve','templates','drafts','create-draft','draft','update-draft','delete-draft','export'])
def test_feature_routes_require_identity(client, method, path, payload):
    response = client.request(method,'/api/v1'+path.format(id=uuid4()),json=payload) if payload is not None else client.request(method,'/api/v1'+path.format(id=uuid4()))
    assert response.status_code == 401


def test_ai_accepted_proof_edit_and_consent(monkeypatch):
    parsed=SimpleNamespace(text='Worked on Python testing.',sections={'summary':'Worked on Python testing.'})
    request=SimpleNamespace(kind='summary',text=parsed.text,use_ai=True,job_description=None)
    enabled=[]
    fake=SimpleNamespace(ai_available=True,rewrite_summary=lambda source,context:SimpleNamespace(original=source,improved='Contributed to Python testing.',source='openai'))
    monkeypatch.setattr(feature_engine,'make_assistant',lambda flag:enabled.append(flag) or fake)
    assert feature_engine.improve_resume(parsed,request,True)[0].source=='openai'
    request.use_ai=False
    feature_engine.improve_resume(parsed,request,True)
    assert enabled==[True,False]


@pytest.mark.parametrize('size,limit,success',[(20,20,True),(21,20,False)],ids=['at-limit','over-limit'])
def test_storage_read_real_http_headers_and_stream_bounds(monkeypatch, size, limit, success, caplog):
    import httpx
    from backend.cloud.storage import PrivateStorage
    secret='sb_secret_synthetic_storage_read_test'
    path=f'{uuid4()}/{uuid4()}.pdf'
    observed=[]
    def provider(request):
        observed.append(request)
        assert request.headers['apikey']==secret
        assert 'authorization' not in request.headers
        if '/bucket/' in request.url.path:
            return httpx.Response(200,json={'public':False})
        assert request.url.path=='/storage/v1/object/authenticated/resumes/'+path
        return httpx.Response(200,content=b'x'*size)
    factory=httpx.Client
    monkeypatch.setattr('backend.cloud.storage.httpx.Client',lambda **kwargs:factory(transport=httpx.MockTransport(provider),**kwargs))
    storage=PrivateStorage(SimpleNamespace(bucket='resumes',supabase_url='https://example.invalid',secret_key=secret))
    if success: assert storage.read(path,limit)==b'x'*size
    else:
        with pytest.raises(ValueError,match='size limit'): storage.read(path,limit)
    assert len(observed)==2 and secret not in caplog.text


def test_match_known_fixture_exact_score():
    result=feature_engine.match_resume(SimpleNamespace(text='Python SQL'),'Python SQL Docker engineer for a team role.')
    assert result.match_score==66.7
    assert result.matching==['python','sql'] and result.missing==['docker']
    assert result.keyword_matching==[]
