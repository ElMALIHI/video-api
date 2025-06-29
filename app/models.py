from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


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


class TextOverlay(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Text content")
    position: Position = Field(..., description="Text position")
    font_size: int = Field(default=24, ge=8, le=200, description="Font size in pixels")
    color: str = Field(default="#FFFFFF", regex=r'^#[0-9A-Fa-f]{6}$', description="Text color in hex format")
    background_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$', description="Background color in hex format")
    start_time: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    duration: Optional[float] = Field(None, ge=0.1, description="Duration in seconds")
    animation: Optional[str] = Field(None, description="Animation type")


class Audio(BaseModel):
    file_id: str = Field(..., description="ID of uploaded audio file")
    volume: float = Field(default=1.0, ge=0.0, le=2.0, description="Volume level (0.0 to 2.0)")
    fade_in: Optional[float] = Field(None, ge=0, description="Fade in duration in seconds")
    fade_out: Optional[float] = Field(None, ge=0, description="Fade out duration in seconds")


class Media(BaseModel):
    type: MediaType = Field(..., description="Type of media")
    file_id: str = Field(..., description="ID of uploaded media file")
    start_time: Optional[float] = Field(None, ge=0, description="Start time for video clips")
    end_time: Optional[float] = Field(None, ge=0, description="End time for video clips")
    effects: Optional[MediaEffects] = Field(None, description="Media effects")

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v is not None and 'start_time' in values and values['start_time'] is not None:
            if v <= values['start_time']:
                raise ValueError('end_time must be greater than start_time')
        return v


class Scene(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, description="Unique scene identifier")
    duration: Optional[float] = Field(None, ge=0.1, description="Scene duration in seconds")
    media: Media = Field(..., description="Main media for the scene")
    audio: Optional[Audio] = Field(None, description="Scene-specific audio")
    text_overlays: Optional[List[TextOverlay]] = Field(default=[], description="Text overlays for the scene")


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


class GlobalAudio(BaseModel):
    background_music: Optional[BackgroundMusic] = Field(None, description="Background music settings")


class VideoSettings(BaseModel):
    width: int = Field(default=1920, ge=480, le=7680, description="Video width in pixels")
    height: int = Field(default=1080, ge=360, le=4320, description="Video height in pixels")
    fps: int = Field(default=30, ge=15, le=60, description="Frames per second")
    duration: Optional[float] = Field(None, ge=1, description="Total video duration in seconds")
    quality: str = Field(default="high", regex=r'^(low|medium|high)$', description="Video quality")


class OutputSettings(BaseModel):
    format: str = Field(default="mp4", regex=r'^(mp4|avi|mov)$', description="Output format")
    codec: str = Field(default="h264", description="Video codec")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CompositionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Video composition title")
    settings: VideoSettings = Field(default_factory=VideoSettings, description="Video settings")
    scenes: List[Scene] = Field(..., min_items=1, max_items=50, description="List of scenes")
    transitions: Optional[List[Transition]] = Field(default=[], description="Scene transitions")
    global_audio: Optional[GlobalAudio] = Field(None, description="Global audio settings")
    watermark: Optional[str] = Field(None, description="Watermark file ID")
    output: OutputSettings = Field(default_factory=OutputSettings, description="Output settings")

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


# Response Models
class UploadResponse(BaseModel):
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    type: str = Field(..., description="File type/mimetype")
    url: Optional[str] = Field(None, description="File URL if applicable")


class JobResponse(BaseModel):
    job_id: int = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(..., ge=0, le=100, description="Job progress percentage")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")


class ComposeResponse(BaseModel):
    job_id: int = Field(..., description="Unique job identifier")
    message: str = Field(..., description="Success message")
    estimated_time: Optional[int] = Field(None, description="Estimated processing time in seconds")


class HealthResponse(BaseModel):
    status: str = Field(..., description="API status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current timestamp")
    uptime: Optional[str] = Field(None, description="Server uptime")
    database: str = Field(..., description="Database status")
    redis: str = Field(..., description="Redis status")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
