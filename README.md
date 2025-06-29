# Video Composition API

A powerful FastAPI-based service for composing videos from multiple media sources including images, video clips, and audio files. The API supports advanced features like transitions, text overlays, background music, and various video effects.

## Features

- **Multi-format Support**: Upload and process images (JPG, PNG, GIF), videos (MP4, AVI, MOV), and audio (MP3, WAV, AAC)
- **Video Composition**: Create complex videos with multiple scenes, transitions, and effects
- **Text Overlays**: Add customizable text with positioning, colors, and animations
- **Background Music**: Include looping background music with volume control
- **Job Management**: Asynchronous processing with real-time status tracking
- **Authentication**: Secure API access with API key authentication
- **Health Monitoring**: Built-in health checks for API and dependencies

## Project Structure

```
video-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── models.py               # Pydantic models and validation
│   ├── auth.py                 # Authentication logic
│   ├── video_processor.py      # Video processing engine
│   ├── endpoints/
│   │   ├── __init__.py
│   │   ├── health.py           # Health check endpoints
│   │   ├── upload.py           # File upload endpoints
│   │   ├── compose.py          # Video composition endpoints
│   │   └── jobs.py             # Job management endpoints
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_video_processor.py
├── database.py                 # Database models and configuration
├── manage_api_keys.py          # API key management utility
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Docker build instructions
└── README.md
```

## Installation

### Prerequisites

- Python 3.8 or higher
- FFmpeg (for video processing)
- Redis (for job queuing)
- Git

### Option 1: Local Installation

1. **Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd video-api
   ```

2. **Install System Dependencies:**
   
   **On Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install ffmpeg redis-server
   sudo systemctl start redis-server
   ```
   
   **On macOS:**
   ```bash
   brew install ffmpeg redis
   brew services start redis
   ```
   
   **On Windows:**
   - Download FFmpeg from https://ffmpeg.org/download.html
   - Install Redis from https://redis.io/download

3. **Create Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8000
   API_RELOAD=true
   DEBUG=true
   
   # Database
   DATABASE_URL=sqlite:///./jobs.db
   
   # Redis
   REDIS_URL=redis://localhost:6379/0
   
   # File Upload
   UPLOAD_DIR=./uploads
   MAX_FILE_SIZE=100MB
   
   # Security
   API_KEYS=your-api-key-here,another-api-key
   
   # CORS (optional)
   CORS_ORIGINS=*
   CORS_CREDENTIALS=true
   CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
   CORS_HEADERS=*
   
   # Logging
   LOG_LEVEL=INFO
   ```

6. **Initialize Database:**
   ```bash
   python -c "from database import create_tables; create_tables()"
   ```

7. **Create Upload Directory:**
   ```bash
   mkdir -p uploads media/renders
   ```

8. **Run the API:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Option 2: Docker Installation

1. **Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd video-api
   ```

2. **Create Environment File:**
   ```bash
   cp .env.example .env  # Edit as needed
   ```

3. **Run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

## API Documentation

Once the server is running, you can access:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **API Status**: http://localhost:8000/

## API Usage Examples

### Authentication

All API endpoints (except health check) require authentication using an API key in the Authorization header:

```bash
curl -H "Authorization: Bearer your-api-key-here" ...
```

### 1. Health Check

**GET** `/api/v1/health`

Check the API and service health status.

```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-06-29T14:00:00Z",
  "database": "healthy",
  "redis": "healthy"
}
```

### 2. Upload Files

**POST** `/api/v1/upload`

Upload media files (images, videos, audio) for use in compositions.

```bash
# Upload single file
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Authorization: Bearer your-api-key-here" \
  -F "files=@/path/to/your/video.mp4"

# Upload multiple files
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Authorization: Bearer your-api-key-here" \
  -F "files=@/path/to/image1.jpg" \
  -F "files=@/path/to/audio.mp3" \
  -F "files=@/path/to/video.mp4"
```

**Response:**
```json
[
  {
    "file_id": "video_a1b2c3d4e5f6",
    "filename": "video.mp4",
    "size": 10485760,
    "type": "video/mp4",
    "url": null
  }
]
```

### 3. Get File Information

**GET** `/api/v1/upload/{file_id}`

Retrieve information about an uploaded file.

```bash
curl -X GET "http://localhost:8000/api/v1/upload/video_a1b2c3d4e5f6" \
  -H "Authorization: Bearer your-api-key-here"
```

### 4. Create Video Composition

**POST** `/api/v1/compose`

Submit a video composition job with scenes, transitions, and effects.

```bash
curl -X POST "http://localhost:8000/api/v1/compose" \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Video Composition",
    "settings": {
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "quality": "high"
    },
    "scenes": [
      {
        "id": "scene1",
        "duration": 5.0,
        "media": {
          "type": "image",
          "file_id": "image_a1b2c3d4e5f6"
        },
        "text_overlays": [
          {
            "text": "Welcome to my video!",
            "position": {"x": "center", "y": "bottom"},
            "font_size": 48,
            "color": "#FFFFFF",
            "start_time": 1.0,
            "duration": 3.0
          }
        ]
      },
      {
        "id": "scene2",
        "duration": 10.0,
        "media": {
          "type": "video",
          "file_id": "video_b2c3d4e5f6g7",
          "start_time": 0,
          "end_time": 10
        }
      }
    ],
    "transitions": [
      {
        "from_scene": "scene1",
        "to_scene": "scene2",
        "type": "fade",
        "duration": 1.0
      }
    ],
    "global_audio": {
      "background_music": {
        "music_ID": "audio_c3d4e5f6g7h8",
        "volume": 0.3,
        "loop": true,
        "fade_in": 2.0,
        "fade_out": 2.0
      }
    }
  }'
```

**Response:**
```json
{
  "job_id": "123",
  "message": "Video composition job 'My Video Composition' has been queued for processing",
  "estimated_time": 45,
  "status": "pending"
}
```

### 5. Check Queue Status

**GET** `/api/v1/compose/queue-status`

Get current queue status and user's job statistics.

```bash
curl -X GET "http://localhost:8000/api/v1/compose/queue-status" \
  -H "Authorization: Bearer your-api-key-here"
```

**Response:**
```json
{
  "user_jobs": {
    "pending": 2,
    "processing": 1,
    "completed": 5,
    "failed": 0,
    "total": 8
  },
  "global_queue": {
    "pending": 10,
    "processing": 3,
    "redis_queue_length": 7
  },
  "status": "healthy"
}
```

### 6. Get User Jobs

**GET** `/api/v1/jobs`

Retrieve a list of your jobs with optional filtering and pagination.

```bash
# Get all jobs
curl -X GET "http://localhost:8000/api/v1/jobs" \
  -H "Authorization: Bearer your-api-key-here"

# Filter by status
curl -X GET "http://localhost:8000/api/v1/jobs?status=completed" \
  -H "Authorization: Bearer your-api-key-here"

# Pagination
curl -X GET "http://localhost:8000/api/v1/jobs?limit=5&offset=10" \
  -H "Authorization: Bearer your-api-key-here"
```

### 7. Get Specific Job Status

**GET** `/api/v1/jobs/{job_id}`

Get detailed status information for a specific job.

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/123" \
  -H "Authorization: Bearer your-api-key-here"
```

**Response:**
```json
{
  "job_id": 123,
  "status": "completed",
  "progress": 100.0,
  "created_at": "2025-06-29T14:00:00Z",
  "updated_at": "2025-06-29T14:02:30Z",
  "started_at": "2025-06-29T14:00:05Z",
  "completed_at": "2025-06-29T14:02:30Z",
  "error": null
}
```

### 8. Cancel Job

**DELETE** `/api/v1/jobs/{job_id}`

Cancel a pending or processing job.

```bash
curl -X DELETE "http://localhost:8000/api/v1/jobs/123" \
  -H "Authorization: Bearer your-api-key-here"
```

**Response:**
```json
{
  "message": "Job 123 has been cancelled",
  "job_id": 123,
  "status": "cancelled"
}
```

## Supported File Formats

### Video Formats
- MP4, AVI, MOV, MKV, FLV, WMV, WebM, M4V

### Image Formats
- JPG, JPEG, PNG, GIF, BMP, TIFF, WebP

### Audio Formats
- MP3, WAV, AAC, OGG, FLAC, M4A, WMA

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API host address |
| `API_PORT` | `8000` | API port number |
| `DATABASE_URL` | `sqlite:///./jobs.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files |
| `MAX_FILE_SIZE` | `100MB` | Maximum file size for uploads |
| `API_KEYS` | - | Comma-separated list of valid API keys |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Key Management

Use the included utility to manage API keys:

```bash
# Generate a new API key
python manage_api_keys.py generate

# List all API keys
python manage_api_keys.py list

# Delete an API key
python manage_api_keys.py delete <api_key>
```

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Code Formatting

```bash
black app/ tests/
flake8 app/ tests/
```

### Type Checking

```bash
mypy app/
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Ensure FFmpeg is installed and in your PATH
2. **Redis connection error**: Verify Redis is running and accessible
3. **Permission denied**: Check file permissions for upload directory
4. **Out of disk space**: Monitor available disk space for uploads and renders

### Logs

Check application logs for detailed error information:

```bash
# If running with Docker
docker-compose logs api

# If running locally, logs will appear in console output
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For questions and support, please open an issue on the repository or contact the development team.
