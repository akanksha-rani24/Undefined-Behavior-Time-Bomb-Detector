import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Boolean, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ScanRecord(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    language = Column(String, default="c")
    source_code = Column(Text, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    opt_levels = Column(JSON, default=["O0", "O2"])
    summary_json = Column(JSON, nullable=True)
    bombs_json = Column(JSON, default=[])
    function_diffs_json = Column(JSON, default=[])
    o0_ir = Column(Text, default="")
    o2_ir = Column(Text, default="")
    o3_ir = Column(Text, default="")
    ir_diff = Column(Text, default="")
    cfg_json = Column(JSON, nullable=True)
    compile_error = Column(Text, nullable=True)
    has_clang = Column(Boolean, default=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
