import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db, SessionLocal
from db.models import Job, Business
from api.schemas import AnalyzeRequest, JobResponse, ReportResponse, BusinessOut, AnalyticsOut
from core.job_queue import create_job, update_job_status, get_job
from agents.crawler import crawl
from agents.extractor import extract_all
from agents.analytics import run_analytics
import json

router = APIRouter()

async def run_pipeline(job_id: str, city: str, category: str, locality: str):
    db = SessionLocal()
    try:
        update_job_status(job_id, "processing", db)
        raw = crawl(city, category, locality)
        if raw:
            print(f"SAMPLE REVIEWS COUNT: {len(raw[0].get('reviews', []))}")
        businesses = extract_all(raw)
        if businesses:
            print(f"SAMPLE COMPLAINTS: {businesses[0].get('top_complaints')}")
            print(f"SAMPLE PRICE RANGE: {businesses[0].get('price_range')}")
        analytics = run_analytics(businesses)
        for b in businesses:
            business = Business(
                id=b.get("id", str(uuid.uuid4())),
                job_id=job_id,
                name=b.get("name"),
                rating=b.get("rating"),
                review_count=b.get("review_count"),
                price_range=b.get("price_range"),
                address=b.get("address"),
                phone=b.get("phone"),
                top_complaints=json.dumps(b.get("top_complaints", [])),
                tags=json.dumps(b.get("tags", [])),
                sentiment_score=b.get("sentiment_score"),
                source=b.get("source")
            )
            db.add(business)
        db.commit()
        update_job_status(job_id, "complete", db)
    except Exception as e:
        print(f"PIPELINE ERROR: {e}")
        update_job_status(job_id, "failed", db)
    finally:
        db.close()

@router.post("/analyze", response_model=JobResponse)
async def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    job_id = create_job(request.city, request.category, db)
    job = get_job(job_id, db)
    asyncio.create_task(run_pipeline(job_id, request.city, request.category, request.locality))
    return JobResponse(
        job_id=job_id,
        status=job.status,
        city=job.city,
        category=job.category,
        created_at=job.created_at
    )

@router.get("/status/{job_id}")
async def status(job_id: str, db: Session = Depends(get_db)):
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job.status}

@router.get("/report/{job_id}", response_model=ReportResponse)
async def report(job_id: str, db: Session = Depends(get_db)):
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=400, detail=f"Job is {job.status}, not complete yet")
    businesses = db.query(Business).filter(Business.job_id == job_id).all()
    raw_businesses = [b.__dict__ for b in businesses]
    analytics = run_analytics(raw_businesses)
    business_list = [
        BusinessOut(
            id=b.id,
            name=b.name,
            rating=b.rating,
            review_count=b.review_count,
            price_range=b.price_range,
            address=b.address,
            phone=b.phone,
            top_complaints=b.top_complaints,
            sentiment_score=b.sentiment_score,
            source=b.source
        ) for index, b in enumerate(businesses)
    ]
    return ReportResponse(
        job_id=job_id,
        city=job.city,
        category=job.category,
        businesses=business_list,
        analytics=AnalyticsOut(**analytics),
        completed_at=job.completed_at
    )
