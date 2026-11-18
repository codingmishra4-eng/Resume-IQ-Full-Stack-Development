"""Windows CMD/Linux local checks; ignores private dotenv and never uses live keys."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from scripts.test_environment import disposable_url, isolated_environment


def main():
    root=Path(__file__).resolve().parents[1]
    environment=isolated_environment(os.environ)
    try:postgres=disposable_url(environment)
    except ValueError:
        print('FAIL: unsafe disposable database opt-in; no checks executed.')
        return 1
    failed=False
    with tempfile.TemporaryDirectory(prefix='resumeiq-local-') as directory:
        report=Path(directory)/'pytest.xml'
        commands=[('pytest',[sys.executable,'-m','pytest','-o','addopts=','-q','--tb=short',f'--junitxml={report}']),
                  ('dependency check',[sys.executable,'-m','pip','check']),
                  ('synthetic smoke',[sys.executable,'smoke_test.py'])]
        for label,command in commands:
            try:
                result=subprocess.run(command,cwd=root,env=environment,capture_output=True,timeout=300)
                passed=result.returncode==0
                failed |= not passed
                if label=='pytest' and report.exists():
                    suites=ET.parse(report).getroot().iter('testsuite')
                    totals={key:0 for key in ('tests','failures','errors','skipped')}
                    for suite in suites:
                        for key in totals:totals[key]+=int(suite.get(key,'0'))
                    count=totals['tests']-totals['failures']-totals['errors']-totals['skipped']
                    print(f"{'PASS' if passed else 'FAIL'}: pytest: {count} passed, {totals['failures']} failed, {totals['skipped']} skipped, {totals['errors']} errors")
                else:print(f"{'PASS' if passed else 'FAIL'}: {label}")
            except Exception:
                failed=True
                print(f'FAIL: {label}; diagnostics suppressed.')
    if postgres is None:print('PENDING: 17 disposable PostgreSQL tests require a fresh local database and explicit opt-in.')
    print('PENDING: Windows execution is verified only when these commands run on Windows; no live services were tested.')
    return int(failed)


if __name__=='__main__':raise SystemExit(main())
