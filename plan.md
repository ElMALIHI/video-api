Build a minimal, focused Video Composition API with just 5 essential endpoints for uploading media, composing videos, checking job status, downloading results, and health monitoring.

Core Endpoints
1. POST /api/v1/upload

Upload multiple media files (images, audio, video)
Returns file IDs for use in composition
Validates file types and sizes
Stores files securely

2. POST /api/v1/compose

Submit video composition job
Uses uploaded file IDs from /upload
Returns job ID for tracking
Accepts composition parameters (scenes, transitions, audio, etc.)

3. GET /api/v1/job-status/{job_id}

Check job status and progress
Returns: pending, processing, completed, failed
Includes error details if failed
Shows progress percentage

4. GET /api/v1/download/{job_id}

Download completed video
Streams the composed video file
Only works for completed jobs

5. GET /api/v1/health

Simple health check endpoint
No authentication required
Returns API status

6. Body Request should be like this:

    "" 
    {
  "title": "My Video Composition",
  "settings": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration": null,
    "quality": "high"
  },
  "scenes": [
    {
      "id": "scene1",
      "duration": null,
      "media": {
        "type": "image",
        "file_id": "img_123456",
        "effects": {
          "zoom": 1.2,
          "pan": "left_to_right",
          "rotation": null
        }
      },
      "audio": {
        "file_id": "audio_789012",
        "volume": 0.8,
        "fade_in": 0.5,
        "fade_out": null
      },
      "text_overlays": [
        {
          "text": "Welcome to our video",
          "position": {"x": "center", "y": "bottom"},
          "font_size": 48,
          "color": "#FFFFFF",
          "background_color": null,
          "start_time": 0.5,
          "duration": 2.0
        }
      ]
    },
    {
      "id": "scene2", 
      "duration": null,
      "media": {
        "type": "video",
        "file_id": "vid_345678",
        "start_time": 0,
        "end_time": null,
        "effects": {
          "speed": 1.0,
          "brightness": null
        }
      }
    },
    {
      "id": "scene3",
      "duration": null,
      "media": {
        "type": "image",
        "file_id": "img_456789"
      },
      "audio": null,
      "text_overlays": [
        {
          "text": "Thank you for watching!",
          "position": {"x": "center", "y": "center"},
          "font_size": 36,
          "color": "#FF0000",
          "animation": null
        }
      ]
    }
  ],
  "transitions": [
    {
      "from_scene": "scene1",
      "to_scene": "scene2",
      "type": "fade",
      "duration": 0.5,
      "easing": null
    },
    {
      "from_scene": "scene2", 
      "to_scene": "scene3",
      "type": "slide_left",
      "duration": 0.8
    }
  ],
  "global_audio": {
    "background_music": {
      "music_ID": "music_999999",
      "volume": 0.3,
      "loop": true,
      "fade_in": 1.0,
      "fade_out": null
    }
  },
  "watermark": null,
  "output": {
    "format": "mp4",
    "codec": "h264",
    "metadata": null
  }
}

""

Tech Stack (Minimal)

Backend: FastAPI
Database: SQLite (for job storage)
Queue: Redis (for job processing)
Video Processing: ffmpeg
Authentication: Multiple API keys (Bearer token)
Deployment: Docker + docker-compose


Project Structure
video-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic models
│   ├── database.py          # SQLite setup
│   ├── auth.py              # Multiple API key auth
│   ├── video_processor.py   # Video composition logic
│   └── endpoints/
│       ├── __init__.py
│       ├── upload.py        # Upload endpoint
│       ├── compose.py       # Compose endpoint
│       ├── jobs.py          # Job status & download
│       └── health.py        # Health check
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md

Core Features (Simplified)

File Upload: Multiple files, basic validation, remote URL support
Video Composition: Basic scenes + transitions + audio
Request Handling: Ignores null values, uses sensible defaults
Job Management: Status tracking, error handling
Authentication: Multiple API keys with job isolation
File Storage: Local filesystem
Output: MP4 format only


API Flow

Upload files → POST /api/v1/upload → Get file IDs
Create composition → POST /api/v1/compose → Get job ID
Check status → GET /api/v1/job-status/{job_id} → Monitor progress
Download result → GET /api/v1/download/{job_id} → Get video


Environment Variables
API_KEYS=key1,key2,key3  # Comma-separated list
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///./jobs.db
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE=100MB
MAX_URL_FILE_SIZE=200MB  # For remote downloads
ALLOWED_DOMAINS=example.com,cdn.example.com  # Optional: restrict URLs

Docker Setup

Single Dockerfile for the API
docker-compose with API + Redis
Volume mounts for file storage
Environment variables for config