"""
Módulo de Base de Datos
Gestiona la conexión con la base de datos PostgreSQL usando SQLAlchemy.
"""
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from src.config import settings

SQLALCHEMY_DATABASE_URL = URL.create(
    "postgresql",
    username=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    host=settings.IP_SERVER,
    port=5432,
    database=settings.DATABASE,
)

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("No se encontró la DATABASE_URL. Asegúrate de configurar el archivo .env.")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Generador de sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
