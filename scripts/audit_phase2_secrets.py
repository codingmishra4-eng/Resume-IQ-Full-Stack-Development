"""Heuristic Git secret audit. Never display matched values or raw Git output."""
import re
import subprocess
from pathlib import Path

PATTERNS = {
    'opaque-api-key': re.compile(r'(?:sb_secret_|sk-(?:proj-)?)[A-Za-z0-9_-]{20,}'),
    'jwt-literal': re.compile(r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'),
    'database-password': re.compile(r'postgres(?:ql)?(?:\+psycopg)?://[^\s:/]+:([^\s@]+)@'),
}


def audit(root):
    findings = {name: 0 for name in PATTERNS}
    def scan(content):
        for category, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                value = match.group(0)
                if any(marker in value.lower() for marker in ('unit_test', 'synthetic', 'placeholder', 'example')):
                    continue
                if category == 'database-password' and match.group(1).lower() in {'password', 'test', 'pass'}:
                    continue
                findings[category] += 1
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True)
        return result.stdout.decode('utf-8', errors='replace')
    paths = git('ls-files', '-z').split('\0')
    for path in filter(None, paths):
        file = root / path
        if file.is_file() and file.stat().st_size < 2_000_000:
            scan(file.read_text(encoding='utf-8', errors='replace'))
    scan(git('log', '--all', '-p', '--format='))
    private_env = [p for p in paths if Path(p).name == '.env' or
                   (Path(p).name.startswith('.env.') and not p.endswith('.example'))]
    return {'candidates': findings, 'tracked_private_env_files': len(private_env)}


def main():
    try:
        result = audit(Path(__file__).resolve().parents[1])
        count = sum(result['candidates'].values()) + result['tracked_private_env_files']
        print(f'Secret audit: {count} candidate exposure(s); values suppressed.')
        print('If confirmed real, rotate with the provider and review access; no rotation performed.' if count
              else 'No candidates detected in scanned tracked files/local history. This is not proof of no prior exposure.')
        return 1 if count else 0
    except Exception:
        print('Secret audit incomplete; raw errors suppressed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
