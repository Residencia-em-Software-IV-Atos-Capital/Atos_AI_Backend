from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import urllib

# Monta connection string ODBC
connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=aquidaba.infonet.com.br,1433;"
    "DATABASE=dbproinfo;"
    "UID=leituraVendas;"
    "PWD=KRphDP65BM;"
    "TrustServerCertificate=yes;"
)

params = urllib.parse.quote_plus(connection_string)

SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

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
