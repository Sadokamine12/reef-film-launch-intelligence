import subprocess
import sys
import uvicorn
from reef.db import engine
from sqlalchemy.orm import Session
from reef.seed import seed
subprocess.run([sys.executable,'-m','alembic','-c','apps/api/alembic.ini','upgrade','head'],check=True)
with Session(engine()) as db: seed(db)
engine().dispose()
uvicorn.run('reef.main:app',host='127.0.0.1',port=8000)
