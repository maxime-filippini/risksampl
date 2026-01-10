from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from worker.settings import settings

database_url = settings.DATABASE_URL

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def connect() -> Session:
    return SessionLocal()


metadata = MetaData()


class Base(DeclarativeBase):
    pass


instruments = Table("instruments", metadata, autoload_with=engine)
portfolios = Table("portfolios", metadata, autoload_with=engine)
investments = Table("investments", metadata, autoload_with=engine)
market_data = Table("market_data", metadata, autoload_with=engine)
ptf_values = Table("ptf_values", metadata, autoload_with=engine)
ptf_comp = Table("ptf_comp", metadata, autoload_with=engine)
measurements = Table("measurements", metadata, autoload_with=engine)
