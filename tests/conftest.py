import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

def pytest_configure(config):
    """
    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest file
    after command line options have been parsed.
    """
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def db_engine():
    """yields a SQLAlchemy engine which is suppressed after the test session"""
    from src.database import engine, Base
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    """yields a SQLAlchemy connection which is rolled back after the test"""
    connection = db_engine.connect()
    # begin the nested transaction
    transaction = connection.begin()
    # use the connection with the already started transaction
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    # roll back the broader transaction
    transaction.rollback()
    # put back the connection to the connection pool
    connection.close()