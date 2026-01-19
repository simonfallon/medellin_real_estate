from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./real_estate.db"

Base = declarative_base()


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, index=True)
    title = Column(String, index=True)
    location = Column(String, index=True)
    price = Column(String)
    area = Column(String)
    bedrooms = Column(String)
    bathrooms = Column(String)
    parking = Column(String)
    estrato = Column(String, nullable=True)
    link = Column(String, unique=True, index=True)
    image_url = Column(String, nullable=True)
    images = Column(String, nullable=True)  # JSON list of images
    source = Column(String, default="arrendamientosenvigadosa")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
