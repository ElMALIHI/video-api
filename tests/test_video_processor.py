"""
Test module for the FFmpeg-based video processor.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from app.video_processor import VideoProcessor
from app.models import (
    ComposeRequest, Scene, Media, VideoSettings, 
    TextOverlay, Position, Transition
)


@pytest.fixture
def video_processor():
    """Create a video processor instance for testing."""
    with patch('redis.from_url') as mock_redis:
        mock_redis.return_value.ping.return_value = True
        processor = VideoProcessor()
        return processor


@pytest.fixture
def sample_compose_request():
    """Create a sample compose request for testing."""
    return ComposeRequest(
        title="Test Video",
        settings=VideoSettings(
            width=1280,
            height=720,
            fps=30,
            quality="medium"
        ),
        scenes=[
            Scene(
                id="scene1",
                duration=5.0,
                media=Media(
                    file_id="test-video-1",
                    type="video"
                ),
                text_overlays=[
                    TextOverlay(
                        text="Hello World",
                        position=Position(x="center", y="center"),
                        font_size=48,
                        color="#FFFFFF",
                        start_time=1.0,
                        duration=3.0
                    )
                ]
            )
        ]
    )


def test_video_processor_initialization(video_processor):
    """Test that video processor initializes correctly."""
    assert video_processor is not None
    assert hasattr(video_processor, 'redis_client')
    assert hasattr(video_processor, 'compose_video')


def test_convert_position(video_processor):
    """Test position conversion functionality."""
    video_size = (1920, 1080)
    
    # Test center position
    center_pos = Position(x="center", y="center")
    x, y = video_processor.convert_position(center_pos, video_size)
    assert x == 960.0
    assert y == 540.0
    
    # Test numeric positions
    numeric_pos = Position(x=100, y=200)
    x, y = video_processor.convert_position(numeric_pos, video_size)
    assert x == 100.0
    assert y == 200.0


def test_update_progress(video_processor):
    """Test progress update functionality."""
    job_id = "test-job-123"
    
    # Mock Redis client
    mock_redis = Mock()
    video_processor.redis_client = mock_redis
    
    video_processor._update_progress(job_id, 50, "processing", "Test message")
    
    # Verify Redis was called
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert f"job:{job_id}" in call_args[0]


def test_get_file_path_not_found(video_processor):
    """Test get_file_path with non-existent file."""
    with pytest.raises(FileNotFoundError):
        video_processor.get_file_path("non-existent-file")


def test_apply_text_overlay(video_processor):
    """Test text overlay application."""
    # Create a mock input stream
    mock_stream = Mock()
    mock_stream.filter.return_value = Mock()
    
    text_overlay = TextOverlay(
        text="Test Text",
        position=Position(x=100, y=100),
        font_size=24,
        color="#FF0000",
        start_time=0.0,
        duration=5.0
    )
    
    video_size = (1920, 1080)
    
    result = video_processor._apply_text_overlay(mock_stream, text_overlay, video_size)
    
    # Verify filter was called
    mock_stream.filter.assert_called_once()
    call_args = mock_stream.filter.call_args
    assert call_args[0][0] == 'drawtext'


def test_apply_video_effects(video_processor):
    """Test video effects application."""
    # Create a mock input stream
    mock_stream = Mock()
    mock_stream.filter.return_value = mock_stream
    
    # Create a mock effects object
    effects = Mock()
    effects.brightness = 1.2
    effects.saturation = 1.1
    effects.speed = 1.0
    effects.zoom = 1.0
    
    result = video_processor._apply_video_effects(mock_stream, effects)
    
    # Verify filter was called for brightness/saturation
    assert mock_stream.filter.called


@patch('ffmpeg.input')
@patch('ffmpeg.output')
def test_compose_video_basic(mock_output, mock_input, video_processor, sample_compose_request):
    """Test basic video composition functionality."""
    # Mock ffmpeg operations
    mock_input_stream = Mock()
    mock_input_stream.video = Mock()
    mock_input_stream.audio = Mock()
    mock_input.return_value = mock_input_stream
    
    # Mock filter operations
    mock_input_stream.video.filter.return_value = mock_input_stream.video
    mock_input_stream.audio.filter.return_value = mock_input_stream.audio
    
    # Mock output
    mock_output_obj = Mock()
    mock_output_obj.overwrite_output.return_value = mock_output_obj
    mock_output_obj.run.return_value = None
    mock_output.return_value = mock_output_obj
    
    # Mock file path resolution
    with patch.object(video_processor, 'get_file_path', return_value='/fake/path/video.mp4'):
        # Mock Redis updates
        with patch.object(video_processor, '_update_progress'):
            # Test the composition
            video_processor.compose_video(sample_compose_request, "test-job-123")
            
            # Verify ffmpeg input was called
            mock_input.assert_called()
            
            # Verify output was called
            mock_output.assert_called()
            
            # Verify run was called
            mock_output_obj.run.assert_called()


def test_ensure_directories(video_processor):
    """Test that required directories are created."""
    # The directories should be created during initialization
    assert Path("media/renders").exists()
    assert Path("temp").exists()
    assert Path("uploads").exists()


if __name__ == "__main__":
    pytest.main([__file__])
