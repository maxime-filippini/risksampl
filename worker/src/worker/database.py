import datetime
import uuid
from decimal import Decimal

from sqlalchemy import Date
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

from worker.settings import settings

database_url = settings.DATABASE_URL

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def connect() -> Session:
    return SessionLocal()


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), default=uuid.uuid4, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), default=uuid.uuid4, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    holdings: Mapped[list["Holding"]] = relationship(
        "Holding",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MarketData(Base):
    __tablename__ = "market_data"

    date: Mapped[datetime.date] = mapped_column(
        Date(),
        primary_key=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data_type: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Float())


class Holding(Base):
    __tablename__ = "holdings"

    as_of: Mapped[datetime.date] = mapped_column(
        Date(),
        primary_key=True,
        default=datetime.date.today,
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=8), nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
    instrument: Mapped["Instrument"] = relationship("Instrument")
