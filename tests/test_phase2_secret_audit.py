"""Secret fixtures are synthetic strings, never real provider credentials."""
from pathlib import Path
import subprocess
from scripts.audit_phase2_secrets import audit


def test_audit_checks_current_and_historical_files_without_emitting_values(tmp_path, capsys):
    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init')
    git('config', 'user.name', 'Synthetic Test')
    git('config', 'user.email', 'synthetic@example.invalid')
    key = 'sb_secret_' + 'Z' * 32
    file = tmp_path / 'historical.txt'
    file.write_text(key)
    git('add', 'historical.txt')
    git('commit', '-m', 'Synthetic historical scanner fixture')
    git('rm', 'historical.txt')
    git('commit', '-m', 'Remove fixture')
    (tmp_path / '.env').write_text('PRIVATE=synthetic-placeholder')
    git('add', '.env')
    result = audit(tmp_path)
    assert result['candidates']['opaque-api-key'] >= 1
    assert result['tracked_private_env_files'] == 1
    assert key not in capsys.readouterr().out
