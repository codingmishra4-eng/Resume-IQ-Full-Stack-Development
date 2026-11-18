import json
from types import SimpleNamespace
from scripts.verify_phase5 import Phase5Verifier, digest
from scripts.verify_phase2 import main
from uuid import uuid4


def test_phase5_no_permission_does_not_access_services(monkeypatch,capsys):
    monkeypatch.setattr('scripts.verify_phase2.create_engine',lambda *a,**k:(_ for _ in ()).throw(AssertionError('network')))
    assert main([],verifier_class=Phase5Verifier)==2
    assert 'PENDING' in capsys.readouterr().out


def test_extended_journal_atomic_and_no_payload_secrets(tmp_path):
    verifier=Phase5Verifier(None,None,None,tmp_path/'journal.json')
    owner=str(uuid4());verifier.drafts[owner]={str(uuid4())}
    verifier.save_journal();data=json.loads(verifier.journal.read_text())
    assert data['phase5']['draft_hash']==digest(verifier.draft_data)
    assert 'Synthetic Verification Candidate' not in verifier.journal.read_text()
    assert data['phase5']['drafts'][owner]


def test_phase5_recovery_never_replays_unverified_identifiers(tmp_path,capsys):
    source=tmp_path/'retain.json';source.write_text('{"phase5": {}}')
    verifier=Phase5Verifier(None,None,None,tmp_path/'unused')
    assert verifier.recover(source)==1
    assert source.read_text()=='{"phase5": {}}'


def test_cleanup_retains_journal_after_ambiguous_draft_write(tmp_path,monkeypatch):
    from scripts.verify_phase2 import Verifier
    verifier=Phase5Verifier(None,None,None,tmp_path/'journal.json')
    verifier.ambiguous_draft=True
    def cleanup(self):
        assert self.ambiguous_upload
        self.save_journal()
        return False
    monkeypatch.setattr(Verifier,'cleanup',cleanup)
    assert not verifier.cleanup()
    assert json.loads(verifier.journal.read_text())['phase5']['ambiguous'] is True


def test_only_confirmed_rate_rejection_is_retried(tmp_path,monkeypatch):
    import httpx
    from scripts.verify_phase2 import Verifier
    response=httpx.Response(429,json={'code':'rate_limited'},headers={'Retry-After':'60'})
    calls=[];waits=[]
    def api(self,*args,**kwargs):calls.append(1);return response if len(calls)==1 else httpx.Response(201,json={})
    monkeypatch.setattr(Verifier,'api',api)
    monkeypatch.setattr('scripts.verify_phase5.time.sleep',lambda delay:waits.append(delay))
    verifier=Phase5Verifier(None,None,None,tmp_path/'journal.json')
    assert verifier.api('POST','/synthetic').status_code==201
    assert len(calls)==2 and waits==[60]
    calls.clear();waits.clear();response=httpx.Response(503,json={})
    assert verifier.api('POST','/synthetic').status_code==503
    assert len(calls)==1 and waits==[]
