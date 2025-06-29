from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid
import os
from pathlib import Path


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class TransitionType(str, Enum):
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    DISSOLVE = "dissolve"
    WIPE = "wipe"


class Position(BaseModel):
    x: Union[str, int] = Field(..., description="X position (can be 'center', 'left', 'right' or pixel value)")
    y: Union[str, int] = Field(..., description="Y position (can be 'center', 'top', 'bottom' or pixel value)")


class MediaEffects(BaseModel):
    zoom: Optional[float] = Field(None, ge=0.1, le=10.0, description="Zoom level (0.1 to 10.0)")
    pan: Optional[str] = Field(None, description="Pan direction (left_to_right, right_to_left, etc.)")
    rotation: Optional[float] = Field(None, ge=-360, le=360, description="Rotation in degrees")
    speed: Optional[float] = Field(None, ge=0.1, le=10.0, description="Video speed multiplier")
    brightness: Optional[float] = Field(None, ge=0.0, le=2.0, description="Brightness adjustment")


class Effect(BaseModel):
    """Video/Audio effect model"""
    type: str = Field(..., description="Effect type (blur, brightness, contrast, etc.)")
    intensity: float = Field(default=1.0, ge=0.0, le=10.0, description="Effect intensity")
    start_time: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    duration: Optional[float] = Field(None, ge=0.1, description="Duration in seconds")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional effect parameters")
    
    @validator('duration')
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v


class TextOverlay(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Text content")
    position: Position = Field(..., description="Text position")
    font_size: int = Field(default=24, ge=8, le=200, description="Font size in pixels")
    color: str = Field(default="#FFFFFF", pattern=r'^#[0-9A-Fa-f]{6}$', description="Text color in hex format")
    background_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Background color for text (optional)")
    start_time: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    duration: Optional[float] = Field(None, ge=0.1, description="Duration in seconds")
    animation: Optional[str] = Field(None, description="Animation type")

class Voiceover(BaseModel):
    file_id: str = Field(..., description="UUID of voiceover audio file")
    volume: float = Field(default=1.0, ge=0.0, le=2.0, description="Volume level (0.0 to 2.0)")
    start_time: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    duration: Optional[float] = Field(None, ge=0.1, description="Duration in seconds")

class Scene(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, description="Unique scene identifier")
    duration: Optional[float] = Field(None, ge=0.1, description="Scene duration in seconds")
    media: Media = Field(..., description="Main media for the scene")
    audio: Optional[Audio] = Field(None, description="Scene-specific audio")
    voiceover: Optional[Voiceover] = Field(None, description="Voiceover for the scene")
    text_overlays: Optional[List[TextOverlay]] = Field(default=[], description="Text overlays for the scene")

    @validator('duration')
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v


class AudioTrack(BaseModel):
    """Audio track model with comprehensive validation"""
    file_id: str = Field(..., description="UUID of uploaded audio file")
    volume: float = Field(default=1.0, ge=0.0, le=2.0, description="Volume level (0.0 to 2.0)")
    fade_in: Optional[float] = Field(None, ge=0, description="Fade in duration in seconds")
    fade_out: Optional[float] = Field(None, ge=0, description="Fade out duration in seconds")
    start_time: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    duration: Optional[float] = Field(None, ge=0.1, description="Duration in seconds")
    loop: bool = Field(default=False, description="Whether to loop the audio")
    effects: Optional[List[Effect]] = Field(default=[], description="Audio effects")
    
    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v
    
    @validator('duration')
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v


class Audio(BaseModel):
    """Legacy Audio model for backward compatibility"""
    file_id: str = Field(..., description="ID of uploaded audio file")
    volume: float = Field(default=1.0, ge=0.0, le=2.0, description="Volume level (0.0 to 2.0)")
    fade_in: Optional[float] = Field(None, ge=0, description="Fade in duration in seconds")
    fade_out: Optional[float] = Field(None, ge=0, description="Fade out duration in seconds")
    
    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v


class Media(BaseModel):
    type: MediaType = Field(..., description="Type of media")
    file_id: str = Field(..., description="ID of uploaded media file")
    start_time: Optional[float] = Field(None, ge=0, description="Start time for video clips")
    end_time: Optional[float] = Field(None, ge=0, description="End time for video clips")
    effects: Optional[MediaEffects] = Field(None, description="Media effects")

    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v is not None and 'start_time' in values and values['start_time'] is not None:
            if v <= values['start_time']:
                raise ValueError('end_time must be greater than start_time')
        return v




class Transition(BaseModel):
    from_scene: str = Field(..., description="Source scene ID")
    to_scene: str = Field(..., description="Target scene ID")
    type: TransitionType = Field(..., description="Transition type")
    duration: float = Field(default=0.5, ge=0.1, le=5.0, description="Transition duration in seconds")
    easing: Optional[str] = Field(None, description="Easing function")


class BackgroundMusic(BaseModel):
    music_ID: str = Field(..., description="ID of uploaded music file")
    volume: float = Field(default=0.3, ge=0.0, le=1.0, description="Background music volume")
    loop: bool = Field(default=True, description="Whether to loop the music")
    fade_in: Optional[float] = Field(None, ge=0, description="Fade in duration")
    fade_out: Optional[float] = Field(None, ge=0, description="Fade out duration")
    
    @validator('music_ID')
    def validate_music_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('music_ID must be a valid UUID')
        return v


class GlobalAudio(BaseModel):
    background_music: Optional[BackgroundMusic] = Field(None, description="Background music settings")


class VideoSettings(BaseModel):
    width: int = Field(default=1920, ge=480, le=7680, description="Video width in pixels")
    height: int = Field(default=1080, ge=360, le=4320, description="Video height in pixels")
    fps: int = Field(default=30, ge=15, le=60, description="Frames per second")
    duration: Optional[float] = Field(None, ge=1, description="Total video duration in seconds")
    quality: str = Field(default="high", pattern=r'^(low|medium|high)$', description="Video quality")


class OutputSettings(BaseModel):
    format: str = Field(default="mp4", pattern=r'^(mp4|avi|mov)$', description="Output format")
    codec: str = Field(default="h264", description="Video codec")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ComposeRequest(BaseModel):
    """Main composition request model with comprehensive validation"""
    title: str = Field(..., min_length=1, max_length=200, description="Video composition title")
    settings: VideoSettings = Field(default_factory=VideoSettings, description="Video settings")
    scenes: List[Scene] = Field(..., min_items=1, max_items=50, description="List of scenes")
    transitions: Optional[List[Transition]] = Field(default=[], description="Scene transitions")
    global_audio: Optional[GlobalAudio] = Field(None, description="Global audio settings")
    watermark: Optional[str] = Field(None, description="Watermark file ID")
    output: OutputSettings = Field(default_factory=OutputSettings, description="Output settings")
    audio_tracks: Optional[List[AudioTrack]] = Field(default=[], description="Additional audio tracks")
    effects: Optional[List[Effect]] = Field(default=[], description="Global effects")

    @validator('scenes')
    def validate_scenes(cls, v):
        scene_ids = [scene.id for scene in v]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError('Scene IDs must be unique')
        return v

    @validator('transitions')
    def validate_transitions(cls, v, values):
        if v and 'scenes' in values:
            scene_ids = {scene.id for scene in values['scenes']}
            for transition in v:
                if transition.from_scene not in scene_ids:
                    raise ValueError(f'from_scene "{transition.from_scene}" not found in scenes')
                if transition.to_scene not in scene_ids:
                    raise ValueError(f'to_scene "{transition.to_scene}" not found in scenes')
        return v
    
    @validator('watermark')
    def validate_watermark_uuid(cls, v):
        if v is not None:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError('watermark must be a valid UUID')
        return v


# Alias for backward compatibility
CompositionRequest = ComposeRequest


# Response Models
class UploadResponse(BaseModel):
    """Response model for file uploads with UUID validation"""
    file_id: str = Field(..., description="Unique file identifier (UUID)")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    type: str = Field(..., description="File type/mimetype")
    url: Optional[str] = Field(None, description="File URL if applicable")
    upload_time: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    
    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v


class JobStatusResponse(BaseModel):
    """Response model for job status queries"""
    job_id: str = Field(..., description="Unique job identifier (UUID)")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(..., ge=0, le=100, description="Job progress percentage")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")
    result_url: Optional[str] = Field(None, description="URL to download result if completed")
    estimated_time_remaining: Optional[int] = Field(None, description="Estimated time remaining in seconds")
    
    @validator('job_id')
    def validate_job_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('job_id must be a valid UUID')
        return v


class JobResponse(BaseModel):
    """Legacy job response model for backward compatibility"""
    job_id: int = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(..., ge=0, le=100, description="Job progress percentage")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")


class ComposeResponse(BaseModel):
    """Response model for composition requests"""
    job_id: str = Field(..., description="Unique job identifier (UUID)")
    message: str = Field(..., description="Success message")
    estimated_time: Optional[int] = Field(None, description="Estimated processing time in seconds")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Initial job status")
    
    @validator('job_id')
    def validate_job_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('job_id must be a valid UUID')
        return v


class HealthResponse(BaseModel):
    status: str = Field(..., description="API status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current timestamp")
    uptime: Optional[str] = Field(None, description="Server uptime")
    database: str = Field(..., description="Database status")
    redis: str = Field(..., description="Redis status")


class DownloadResponse(BaseModel):
    """Response model for download requests"""
    download_url: str = Field(..., description="Presigned URL or direct download path")
    file_id: str = Field(..., description="File identifier (UUID)")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    expires_at: Optional[datetime] = Field(None, description="URL expiration timestamp")
    content_type: str = Field(..., description="MIME type of the file")
    
    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# Utility validators and functions
def validate_file_exists(file_path: str) -> bool:
    """Check if a file exists at the given path"""
    return Path(file_path).exists() and Path(file_path).is_file()


def validate_uuid_format(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def validate_duration_positive(duration: Optional[float]) -> bool:
    """Validate that duration is positive if provided"""
    return duration is None or duration > 0


# Enhanced models with file existence validation
class MediaFileReference(BaseModel):
    """Model for media file references with file existence validation"""
    file_id: str = Field(..., description="UUID of the file")
    file_path: Optional[str] = Field(None, description="Local file path for validation")
    
    @validator('file_id')
    def validate_file_id_uuid(cls, v):
        if not validate_uuid_format(v):
            raise ValueError('file_id must be a valid UUID')
        return v
    
    @validator('file_path')
    def validate_file_path_exists(cls, v):
        if v is not None and not validate_file_exists(v):
            raise ValueError(f'File does not exist at path: {v}')
        return v


class BatchUploadResponse(BaseModel):
    """Response model for batch file uploads"""
    files: List[UploadResponse] = Field(..., description="List of uploaded files")
    total_count: int = Field(..., description="Total number of files processed")
    success_count: int = Field(..., description="Number of successfully uploaded files")
    failed_count: int = Field(..., description="Number of failed uploads")
    errors: Optional[List[str]] = Field(default=[], description="List of error messages for failed uploads")
