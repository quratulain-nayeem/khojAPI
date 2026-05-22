import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from db.models import Job

def create_job(city: str, category: str, db: Session) -> str:
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        city=city,
        category=category,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    return job_id

def update_job_status(job_id: str, status: str, db: Session):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = status
        if status == "complete":
            job.completed_at = datetime.utcnow()
        db.commit()

def get_job(job_id: str, db: Session) -> Job:
    return db.query(Job).filter(Job.id == job_id).first()