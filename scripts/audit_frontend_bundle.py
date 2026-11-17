"""Heuristic built-public-artifact secret audit; emit counts only."""
from pathlib import Path
from scripts.audit_phase2_secrets import PATTERNS


def audit(root):
    files=list(root.rglob('*.js'))
    if not files: raise ValueError('Build the frontend first')
    candidates=0
    for file in files:
        content=file.read_text(errors='replace')
        for pattern in PATTERNS.values():
            for match in pattern.finditer(content):
                if not any(marker in match.group().lower() for marker in ('synthetic','unit_test','placeholder','example')):
                    candidates+=1
    return candidates


def main():
    try:
        count=audit(Path('web/.next/static'))
        print(f'Public bundle scan: {count} candidate exposure(s); values suppressed. Heuristic only.')
        return int(count>0)
    except Exception:
        print('Public bundle scan incomplete; values suppressed.')
        return 1


if __name__=='__main__':raise SystemExit(main())
