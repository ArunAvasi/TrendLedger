from sqlalchemy import (
    Column, Integer, String, Date, DateTime, BigInteger, Numeric,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(16), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class CompanySnapshot(Base):
    __tablename__ = "company_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "snapshot_date", name="uq_company_snapshot"),
    )

    id = Column(Integer, primary_key=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    snapshot_date = Column(Date, nullable=False, index=True)

    market_cap     = Column(BigInteger,   nullable=True)
    pe_ttm         = Column(Numeric(14, 4), nullable=True)
    pe_fwd         = Column(Numeric(14, 4), nullable=True)
    price_to_sales = Column(Numeric(14, 4), nullable=True)
    ev_to_ebitda   = Column(Numeric(14, 4), nullable=True)
    price_to_book  = Column(Numeric(14, 4), nullable=True)
    fcf_yield      = Column(Numeric(14, 4), nullable=True)

    profit_margin        = Column(Numeric(8, 4), nullable=True)
    operating_margin_ttm = Column(Numeric(8, 4), nullable=True)
    earnings_yoy         = Column(Numeric(8, 4), nullable=True)
    revenue_yoy          = Column(Numeric(8, 4), nullable=True)

    cash     = Column(BigInteger, nullable=True)
    debt     = Column(BigInteger, nullable=True)
    net_cash = Column(BigInteger, nullable=True)

    dividend_yield = Column(Numeric(8, 4), nullable=True)
    payout_ratio   = Column(Numeric(8, 4), nullable=True)
    ex_div_date    = Column(Date,           nullable=True)
    payout_date    = Column(Date,           nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
