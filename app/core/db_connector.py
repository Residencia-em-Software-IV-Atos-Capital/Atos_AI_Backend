from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Usando IP diretamente em vez do hostname
SQLALCHEMY_DATABASE_URL = "mssql+pymssql://leituraVendas:KRphDP65BM@177.47.187.11:1433/dbproinfo"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependência p/ injeção
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()