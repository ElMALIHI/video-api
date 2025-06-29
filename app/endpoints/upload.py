from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import os
import uuid
import hashlib
import mimetypes
from pathlib import Path
import logging
import aiofiles
from app.models import UploadResponse
from app.auth import get_current_user, AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "100MB").replace("MB", "")) * 1024 * 1024  # Convert MB to bytes
ALLOWED_EXTENSIONS = {
    # Video formats
    ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v",
    # Image formats  
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    # Audio formats
    ".mp3", ".wav", ".aac", ".ogg", ".flac", ".m4a", ".wma"
}

def ensure_upload_dir():
    """Ensure upload directory exists."""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

def validate_file_type(filename: str) -> str:
    """
    Validate file type based on extension.
    
    Args:
        filename: The filename to validate
        
    Returns:
        str: The file type category (image, video, audio)
        
    Raises:
        HTTPException: If file type is not allowed
    """
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type {file_ext} is not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Determine file category
    if file_ext in {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v"}:
        return "video"
    elif file_ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}:
        return "image"
    elif file_ext in {".mp3", ".wav", ".aac", ".ogg", ".flac", ".m4a", ".wma"}:
        return "audio"
    else:
        return "unknown"

def generate_file_id(filename: str, user_id: str) -> str:
    """
    Generate a unique file ID.
    
    Args:
        filename: Original filename
        user_id: User identifier
        
    Returns:
        str: UUID file ID
    """
    return str(uuid.uuid4())

async def save_uploaded_file(upload_file: UploadFile, file_id: str) -> str:
    """
    Save uploaded file to disk.
    
    Args:
        upload_file: The uploaded file
        file_id: Unique file identifier
        
    Returns:
        str: Path to saved file
        
    Raises:
        HTTPException: If file cannot be saved
    """
    ensure_upload_dir()
    
    # Get file extension
    file_ext = Path(upload_file.filename).suffix.lower()
    filename = f"{file_id}{file_ext}"
    file_path = Path(UPLOAD_DIR) / filename
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await upload_file.read()
            await f.write(content)
        
        logger.info(f"Saved file {filename} ({len(content)} bytes)")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Failed to save file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save file")

@router.post("/upload", response_model=List[UploadResponse])
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Upload multiple media files (images, audio, video).
    
    This endpoint allows uploading multiple files simultaneously.
    Each file is validated for type and size, then stored securely.
    Returns file IDs that can be used in video composition requests.
    
    Args:
        files: List of files to upload
        current_user: Authenticated user
        
    Returns:
        List[UploadResponse]: List of upload results with file IDs
        
    Raises:
        HTTPException: If files are invalid or upload fails
    """
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > 10:  # Limit number of files per request
        raise HTTPException(status_code=400, detail="Too many files. Maximum 10 files per request.")
    
    uploaded_files = []
    
    for upload_file in files:
        # Validate file size
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        
        # Read file to check size
        content = await upload_file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File {upload_file.filename} is too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File {upload_file.filename} is empty"
            )
        
        # Reset file pointer
        await upload_file.seek(0)
        
        # Validate file type
        file_type = validate_file_type(upload_file.filename)
        
        # Generate unique file ID
        file_id = generate_file_id(upload_file.filename, current_user.user_id)
        
        # Save file
        file_path = await save_uploaded_file(upload_file, file_id)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(upload_file.filename)
        if not mime_type:
            mime_type = upload_file.content_type or "application/octet-stream"
        
        uploaded_files.append(UploadResponse(
            file_id=file_id,
            filename=upload_file.filename,
            size=file_size,
            type=mime_type,
            url=None  # We don't expose direct URLs for security
        ))
        
        logger.info(f"Successfully uploaded file: {file_id} ({upload_file.filename})")
    
    return uploaded_files

@router.get("/upload/{file_id}")
async def get_file_info(
    file_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get information about an uploaded file.
    
    Args:
        file_id: The file identifier
        current_user: Authenticated user
        
    Returns:
        dict: File information
        
    Raises:
        HTTPException: If file not found
    """
    # This is a basic implementation - in production you'd want to store
    # file metadata in the database and check user permissions
    
    # Look for file with this ID in upload directory
    upload_path = Path(UPLOAD_DIR)
    matching_files = list(upload_path.glob(f"{file_id}.*"))
    
    if not matching_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = matching_files[0]
    file_stats = file_path.stat()
    
    return {
        "file_id": file_id,
        "filename": file_path.name,
        "size": file_stats.st_size,
        "created_at": file_stats.st_ctime,
        "exists": True
    }
