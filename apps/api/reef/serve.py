"""Single-service deployment entrypoint; run migrations before starting workers."""
import os
import subprocess
import sys
from pathlib import Path
import uvicorn
from sqlalchemy.orm import Session
from reef.db import engine
from reef.seed import seed
from reef.auth import password_hash
from reef.models import UserAccount

def main():
    root = Path(__file__).resolve().parents[3]
    config = root / 'apps/api/alembic.ini'
    if not config.exists():
        config = Path('/app/apps/api/alembic.ini')
    subprocess.run([sys.executable, '-m', 'alembic', '-c', str(config), 'upgrade', 'head'], check=True)
    with Session(engine()) as db:
        seed(db)
        email = os.environ.get('REEF_ADMIN_EMAIL','').strip().casefold()
        password = os.environ.get('REEF_ADMIN_PASSWORD','')
        if email and not db.get(UserAccount,email):
            if len(password)<12:
                raise RuntimeError('Bootstrap administrator password must contain at least 12 characters')
            db.add(UserAccount(email=email,password_hash=password_hash(password),role='editor',active=True))
            db.commit()
    engine().dispose()
    uvicorn.run('reef.main:app',host='0.0.0.0',port=int(os.environ.get('PORT','8000')),proxy_headers=False)

if __name__=='__main__':
    main()
