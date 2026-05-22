from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AnalyzeRequest(BaseModel):
    city: str
    category: str

class JobResponse(BaseModel):
    job_id: str
    status: str
    city: str
    category: str
    created_at: datetime

class BusinessOut(BaseModel):
    id: str
    name: str
    rating: Optional[float]
    review_count: Optional[int]
    price_range: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    top_complaints: Optional[str]
    sentiment_score: Optional[float]
    source: str

class AnalyticsOut(BaseModel):
    total_businesses: int
    avg_rating: float
    competition_density: str
    underserved_price_band: Optional[str]
    common_complaints: Optional[str]

class ReportResponse(BaseModel):
    job_id: str
    city: str
    category: str
    businesses: list[BusinessOut]
    analytics: AnalyticsOut
    completed_at: Optional[datetime]