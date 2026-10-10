#from collections.abc import AsyncGenerator
#
#from sqlalchemy import create_engine
#from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
#
#from app.config import get_settings
#
#settings = get_settings()
#
#engine = create_engine(
#    settings.database_url,
#    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
#    echo=settings.app_env == "development",
#)
#
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#
#
#class Base(DeclarativeBase):
#    pass
#
#
#def init_db() -> None:
#    from app import models  # noqa: F401
#    Base.metadata.create_all(bind=engine)
#
#
#async def get_db() -> AsyncGenerator[Session, None]:
#    db = SessionLocal()
#    try:
#        yield db
#    finally:
#        db.close()
#
#
#def get_db_session() -> Session:
#    return SessionLocal()
