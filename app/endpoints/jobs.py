from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import logging
from datetime import datetime

from app.models import JobResponse, JobStatusResponse
from app.auth import get_current_user, AuthenticatedUser
from database import get_db, Job

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/jobs", response_model=List[JobResponse])
async def get_user_jobs(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(10, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip")
):
    """
    Get list of user's jobs with optional filtering.
    
    Args:
        current_user: Authenticated user
        db: Database session
        status: Optional status filter
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip for pagination
        
    Returns:
        List[JobResponse]: List of user's jobs
    """
    
    try:
        query = db.query(Job).filter(Job.api_key == current_user.api_key)
        
        if status:
            query = query.filter(Job.status == status)
        
        jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
        
        return [JobResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error=job.error
        ) for job in jobs]
        
    except Exception as e:
        logger.error(f"Failed to get user jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get status of a specific job.
    
    Args:
        job_id: Job identifier
        current_user: Authenticated user
        db: Database session
        
    Returns:
        JobResponse: Job status information
        
    Raises:
        HTTPException: If job not found or access denied
    """
    
    try:
        job = db.query(Job).filter(
            Job.id == job_id,
            Job.api_key == current_user.api_key
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error=job.error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")

@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a pending or processing job.
    
    Args:
        job_id: Job identifier
        current_user: Authenticated user
        db: Database session
        
    Returns:
        dict: Cancellation confirmation
        
    Raises:
        HTTPException: If job not found, access denied, or cannot be cancelled
    """
    
    try:
        job = db.query(Job).filter(
            Job.id == job_id,
            Job.api_key == current_user.api_key
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status in ["completed", "failed"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot cancel job with status: {job.status}"
            )
        
        # Update job status to failed with cancellation message
        job.status = "failed"
        job.error = "Job cancelled by user"
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Job {job_id} cancelled by user {current_user.user_id}")
        
        return {
            "message": f"Job {job_id} has been cancelled",
            "job_id": job_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")
