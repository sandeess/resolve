from sqlmodel import create_engine

from app.core import rls
from app.core.config import settings

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)

rls.install()
