"""Generate synthetic DOCX bytes for opt-in browser QA. Never reads a resume."""
import base64
import hashlib
import json
from pathlib import Path
from scripts.verify_phase2 import documents


def main():
    data=documents()['.docx']
    target=Path('work/phase5-browser-document.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({'bytes':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()}))
    print('Synthetic browser fixture generated; no personal document read.')


if __name__=='__main__':main()
