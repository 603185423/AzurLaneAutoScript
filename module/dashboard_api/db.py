import os

from sqlalchemy import BIGINT, BOOLEAN, Column, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class DashboardApiUser(Base):
    __tablename__ = "dashboard_api_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_key = Column(String(64), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    is_active = Column(BOOLEAN, nullable=False, default=True)
    created_at_ms = Column(BIGINT, nullable=False)
    updated_at_ms = Column(BIGINT, nullable=False)

    samples = relationship("DashboardResourceSample", back_populates="user")


class DashboardResourceSample(Base):
    __tablename__ = "dashboard_resource_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("dashboard_api_users.id"), nullable=False, index=True)
    resource_name = Column(String(64), nullable=False, index=True)
    recorded_at_ms = Column(BIGINT, nullable=False, index=True)
    received_at_ms = Column(BIGINT, nullable=False)
    value = Column(Integer, nullable=False)
    limit_value = Column(Integer, nullable=True)
    total_value = Column(Integer, nullable=True)
    color = Column(String(16), nullable=True)
    source_instance = Column(String(128), nullable=True)
    source_config = Column(String(128), nullable=True)

    user = relationship("DashboardApiUser", back_populates="samples")


class DashboardResourceLatest(Base):
    __tablename__ = "dashboard_resource_latest"
    __table_args__ = (UniqueConstraint("user_id", "resource_name", name="uq_dashboard_latest_user_resource"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("dashboard_api_users.id"), nullable=False, index=True)
    resource_name = Column(String(64), nullable=False, index=True)
    recorded_at_ms = Column(BIGINT, nullable=False, index=True)
    received_at_ms = Column(BIGINT, nullable=False)
    value = Column(Integer, nullable=False)
    limit_value = Column(Integer, nullable=True)
    total_value = Column(Integer, nullable=True)
    color = Column(String(16), nullable=True)


class Database:
    def __init__(self, url: str):
        self.url = url
        self.engine = create_engine(url, **self._engine_kwargs(url))
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    @staticmethod
    def _engine_kwargs(url: str):
        kwargs = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite:///"):
            db_path = url.replace("sqlite:///", "", 1)
            directory = os.path.dirname(os.path.abspath(db_path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            kwargs["connect_args"] = {"check_same_thread": False}
        return kwargs

    @property
    def dialect_name(self) -> str:
        return self.engine.url.get_backend_name()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self):
        return self.SessionLocal()
