from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import json
import logging
import redis
from datetime import datetime
import os

from app.models import CompositionRequest, ComposeResponse
from app.auth import get_current_user, AuthenticatedUser
from database import get_db, Job
from app.video_processor import video_processor

logger = logging.getLogger(__name__)

router = APIRouter()

# Redis connection for job queue
def get_redis():
    """Get Redis connection."""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to create Redis connection: {e}")
        return None

def estimate_processing_time(request: CompositionRequest) -> int:
    """
    Estimate processing time based on composition complexity.
    
    Args:
        request: Composition request
        
    Returns:
        int: Estimated time in seconds
    """
    base_time = 30  # Base processing time
    
    # Add time per scene
    scene_time = len(request.scenes) * 15
    
    # Add time for transitions
    transition_time = len(request.transitions or []) * 5
    
    # Add time for text overlays
    text_overlay_count = sum(len(scene.text_overlays or []) for scene in request.scenes)
    text_time = text_overlay_count * 3
    
    # Add time for voiceovers
    voiceover_count = sum(1 for scene in request.scenes if scene.voiceover)
    voiceover_time = voiceover_count * 5
    
    # Add time for background music
    music_time = 10 if request.global_audio and request.global_audio.background_music else 0
    
    # Quality multiplier
    quality_multiplier = {
        "low": 0.7,
        "medium": 1.0,
        "high": 1.5
    }.get(request.settings.quality, 1.0)
    
    total_time = (base_time + scene_time + transition_time + text_time + voiceover_time + music_time) * quality_multiplier
    
    return int(total_time)

async def process_video_job(job_id: int, composition_data: str, api_key: str):
    """
    Background task to process video composition.
    
    Args:
        job_id: Database job ID
        composition_data: JSON string of composition request
        api_key: API key for the user
    """
    db = next(get_db())
    
    try:
        # Get job from database
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in database")
            return
        
        # Update job status to processing
        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.progress = 0.0
        db.commit()
        
        logger.info(f"Starting processing for job {job_id}")
        
        # Parse composition request
        composition_dict = json.loads(composition_data)
        request = CompositionRequest(**composition_dict)
        
        # Process the video using new FFmpeg-based processor
        video_processor.compose_video(request, str(job_id))
        
        # Set output path (the video processor saves to media/renders/{job_id}.mp4)
        output_path = f"media/renders/{job_id}.mp4"
        
        # Update job as completed
        job.status = "completed"
        job.progress = 100.0
        job.output_path = output_path
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        
        # Update job as failed
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job {job_id} status: {str(db_error)}")
    
    finally:
        db.close()

@router.post("/compose", response_model=ComposeResponse)
async def create_composition(
    request: CompositionRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a video composition job.
    
    This endpoint accepts a composition request with scenes, transitions, 
    audio, and other settings, then queues it for processing.
    
    Args:
        request: Video composition specification
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        db: Database session
        
    Returns:
        ComposeResponse: Job information including job ID
        
    Raises:
        HTTPException: If the request is invalid or job creation fails
    """
    
    logger.info(f"Received composition request: {request.title}")
    
    try:
        # Validate that all referenced files exist
        file_ids = set()
        
        # Collect file IDs from scenes
        for scene in request.scenes:
            file_ids.add(scene.media.file_id)
            if scene.audio:
                file_ids.add(scene.audio.file_id)
            if scene.voiceover:
                file_ids.add(scene.voiceover.file_id)
        
        # Collect file IDs from global audio
        if request.global_audio and request.global_audio.background_music:
            file_ids.add(request.global_audio.background_music.music_ID)
        
        # Collect watermark file ID
        if request.watermark:
            file_ids.add(request.watermark)
        
        # Validate all files exist
        missing_files = []
        for file_id in file_ids:
            try:
                video_processor.get_file_path(file_id)
            except FileNotFoundError:
                missing_files.append(file_id)
        
        if missing_files:
            raise HTTPException(
                status_code=400,
                detail=f"The following files were not found: {', '.join(missing_files)}"
            )
        
        # Estimate processing time
        estimated_time = estimate_processing_time(request)
        
        # Create job record in database
        job = Job(
            api_key=current_user.api_key,
            status="pending",
            progress=0.0,
            input_json=request.json(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(f"Created job {job.id} for user {current_user.user_id}")
        
        # Queue the job for background processing
        background_tasks.add_task(
            process_video_job,
            job.id,
            request.json(),
            current_user.api_key
        )
        
        # Try to add to Redis queue as well (optional)
        try:
            r = get_redis()
            if r is not None:
                r.lpush("video_jobs", json.dumps({
                    "job_id": job.id,
                    "api_key": current_user.api_key,
                    "created_at": job.created_at.isoformat()
                }))
            else:
                logger.warning("Redis client is unavailable, skipping queue operation")
        except Exception as e:
            logger.warning(f"Failed to add job to Redis queue: {str(e)}")
            # Continue without Redis - the background task will still run
        
        return ComposeResponse(
            job_id=str(job.id),
            message=f"Video composition job '{request.title}' has been queued for processing",
            estimated_time=estimated_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create composition job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create composition job. Please try again."
        )

@router.get("/compose/queue-status")
async def get_queue_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current queue status and user's job counts.
    
    Args:
        current_user: Authenticated user
        db: Database session
        
    Returns:
        dict: Queue status information
    """
    
    try:
        # Get user's job counts
        user_jobs = db.query(Job).filter(Job.api_key == current_user.api_key)
        
        pending_count = user_jobs.filter(Job.status == "pending").count()
        processing_count = user_jobs.filter(Job.status == "processing").count()
        completed_count = user_jobs.filter(Job.status == "completed").count()
        failed_count = user_jobs.filter(Job.status == "failed").count()
        
        # Get overall queue stats
        total_pending = db.query(Job).filter(Job.status == "pending").count()
        total_processing = db.query(Job).filter(Job.status == "processing").count()
        
        # Try to get Redis queue length
        redis_queue_length = None
        try:
            r = get_redis()
            if r is not None:
                redis_queue_length = r.llen("video_jobs")
            else:
                logger.warning("Redis client is unavailable")
        except Exception as e:
            logger.warning(f"Failed to get Redis queue length: {str(e)}")
        
        return {
            "user_jobs": {
                "pending": pending_count,
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count,
                "total": pending_count + processing_count + completed_count + failed_count
            },
            "global_queue": {
                "pending": total_pending,
                "processing": total_processing,
                "redis_queue_length": redis_queue_length
            },
            "status": "healthy"
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get queue status"
        )
