from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from db.database import Base
import datetime

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    city = Column(String, nullable=False)
    category = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Business(Base):
    __tablename__ = "businesses"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False)
    name = Column(String)
    rating = Column(Float)
    review_count = Column(Integer)
    price_range = Column(String)
    address = Column(String)
    phone = Column(String)
    top_complaints = Column(Text)
    tags = Column(Text)
    sentiment_score = Column(Float)
    source = Column(String)
