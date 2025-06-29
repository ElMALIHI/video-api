import os
import logging
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
import ffmpeg
import redis
import uuid

from app.models import ComposeRequest, Scene, Transition, TextOverlay, Position

logger = logging.getLogger(__name__)

# Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
TEMP_DIR = os.getenv("TEMP_DIR", "./temp")
RENDERS_DIR = Path("media/renders")

class VideoProcessor:
    """
    Video processor that handles video composition using FFmpeg-python.
    
    The processor supports:
    - Concatenating video scenes
    - Applying transitions via xfade
    - Overlaying text on video
    - Mixing audio tracks
    - Adding visual effects (brightness, saturation, etc.)
    """
    
    def __init__(self):
        self.redis_client = None
        self.ensure_directories()
        self._setup_redis()
    
    def _setup_redis(self):
        """Setup Redis connection for progress updates."""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Progress updates will be disabled.")
            self.redis_client = None
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [TEMP_DIR, RENDERS_DIR, Path(UPLOAD_DIR)]:
            directory_path = Path(directory)
            directory_path.mkdir(parents=True, exist_ok=True)
            # Ensure the directory is writable
            try:
                if directory_path.exists():
                    # Test write permissions by creating a temporary file
                    test_file = directory_path / ".write_test"
                    test_file.touch()
                    test_file.unlink()  # Remove test file
                    logger.debug(f"Directory {directory} is writable")
            except Exception as e:
                logger.warning(f"Directory {directory} may not be writable: {e}")
    
    def get_file_path(self, file_id: str) -> str:
        """
        Get the file path for a given file ID.
        
        Args:
            file_id: The file identifier
            
        Returns:
            str: Full path to the file
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        upload_path = Path(UPLOAD_DIR)
        matching_files = list(upload_path.glob(f"{file_id}.*"))
        
        if not matching_files:
            raise FileNotFoundError(f"File with ID {file_id} not found")
        
        return str(matching_files[0])
    
    def convert_position(self, position: Position, video_size: Tuple[int, int]) -> Tuple[float, float]:
        """
        Convert position to pixel coordinates.
        
        Args:
            position: Position object with x, y coordinates
            video_size: Tuple of (width, height)
            
        Returns:
            Tuple[float, float]: Pixel coordinates (x, y)
        """
        width, height = video_size
        
        # Handle X coordinate
        if isinstance(position.x, str):
            if position.x.lower() == "center":
                x = width / 2
            elif position.x.lower() == "left":
                x = 0
            elif position.x.lower() == "right":
                x = width
            else:
                x = float(position.x)
        else:
            x = float(position.x)
        
        # Handle Y coordinate
        if isinstance(position.y, str):
            if position.y.lower() == "center":
                y = height / 2
            elif position.y.lower() == "top":
                y = 0
            elif position.y.lower() == "bottom":
                y = height
            else:
                y = float(position.y)
        else:
            y = float(position.y)
        
        return (x, y)
    
    def _update_progress(self, job_id: str, progress: int, status: str = "processing", message: str = ""):
        """Update job progress in Redis."""
        if self.redis_client:
            try:
                progress_data = {
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.redis_client.set(f"job:{job_id}", json.dumps(progress_data), ex=3600)  # Expire in 1 hour
                logger.debug(f"Updated progress for job {job_id}: {progress}%")
            except Exception as e:
                logger.warning(f"Failed to update progress in Redis for job {job_id}: {e}")
        else:
            logger.debug(f"Redis unavailable, skipping progress update for job {job_id}: {progress}%")
    
    def _apply_text_overlay(self, input_stream, text_overlay: TextOverlay, video_size: Tuple[int, int]):
        """Apply text overlay using FFmpeg drawtext filter."""
        x, y = self.convert_position(text_overlay.position, video_size)
        
        # Convert hex color to format FFmpeg understands
        color = text_overlay.color.replace('#', '0x')
        
        # Build drawtext filter
        drawtext_params = {
            'text': text_overlay.text.replace(':', '\\:').replace("'", "\\'"),
            'fontcolor': color,
            'fontsize': text_overlay.font_size,
            'x': int(x),
            'y': int(y)
        }
        
        if text_overlay.start_time is not None:
            drawtext_params['enable'] = f'gte(t,{text_overlay.start_time})'
            if text_overlay.duration is not None:
                end_time = text_overlay.start_time + text_overlay.duration
                drawtext_params['enable'] += f'*lt(t,{end_time})'
        
        return input_stream.filter('drawtext', **drawtext_params)
    
    def _apply_video_effects(self, input_stream, effects):
        """Apply video effects using FFmpeg filters."""
        if not effects:
            return input_stream
        
        filters = []
        
        # Brightness and saturation effects
        eq_params = {}
        if effects.brightness is not None:
            eq_params['brightness'] = effects.brightness - 1.0  # FFmpeg eq filter expects adjustment from 0
        if hasattr(effects, 'saturation') and effects.saturation is not None:
            eq_params['saturation'] = effects.saturation
        
        if eq_params:
            input_stream = input_stream.filter('eq', **eq_params)
        
        # Speed effects
        if effects.speed is not None and effects.speed != 1.0:
            input_stream = input_stream.filter('setpts', f'PTS/{effects.speed}')
        
        # Zoom effects (scale filter)
        if effects.zoom is not None and effects.zoom != 1.0:
            input_stream = input_stream.filter('scale', f'iw*{effects.zoom}', f'ih*{effects.zoom}')
        
        return input_stream
    
    def _apply_transitions(self, clips, transitions: List[Transition]):
        """Apply transitions between clips using FFmpeg xfade filter."""
        if not transitions or len(clips) < 2:
            return ffmpeg.concat(*clips, v=1, a=1) if len(clips) > 1 else clips[0]
        
        # Create transition map
        transition_map = {}
        for transition in transitions:
            transition_map[(transition.from_scene, transition.to_scene)] = transition
        
        result = clips[0]
        
        for i in range(1, len(clips)):
            # Check if there's a transition defined for this clip pair
            transition_key = (f"scene_{i-1}", f"scene_{i}")  # Simplified scene ID mapping
            
            if transition_key in transition_map:
                transition = transition_map[transition_key]
                
                # Apply xfade transition
                if transition.type == "fade":
                    result = ffmpeg.filter([result, clips[i]], 'xfade', 
                                         transition='fade', 
                                         duration=transition.duration, 
                                         offset=0)
                elif transition.type == "dissolve":
                    result = ffmpeg.filter([result, clips[i]], 'xfade', 
                                         transition='dissolve', 
                                         duration=transition.duration, 
                                         offset=0)
                elif transition.type == "wipe":
                    result = ffmpeg.filter([result, clips[i]], 'xfade', 
                                         transition='wipeleft', 
                                         duration=transition.duration, 
                                         offset=0)
                else:
                    # Default fade for unsupported transitions
                    result = ffmpeg.filter([result, clips[i]], 'xfade', 
                                         transition='fade', 
                                         duration=transition.duration, 
                                         offset=0)
            else:
                # No transition, just concat
                result = ffmpeg.concat(result, clips[i], v=1, a=1)
        
        return result
    
    def compose_video(self, compose_request: ComposeRequest, job_id: str):
        """
        Compose video using FFmpeg-python based on the compose request.
        
        Args:
            compose_request: The request object containing video composition details
            job_id: Unique job identifier for file naming
        """
        output_file = RENDERS_DIR / f"{job_id}.mp4"
        logger.info(f"Starting video composition for job {job_id}")
        
        self._update_progress(job_id, 0, "started", "Initializing video composition")
        
        try:
            video_streams = []
            audio_streams = []
            
            # Process each scene
            for index, scene in enumerate(compose_request.scenes):
                logger.info(f"Processing scene {scene.id}")
                self._update_progress(job_id, int((index / len(compose_request.scenes)) * 40), 
                                    "processing", f"Processing scene {scene.id}")
                
                # Get input file
                file_path = self.get_file_path(scene.media.file_id)
                input_stream = ffmpeg.input(file_path)
                
                # Get video stream
                video_stream = input_stream.video
                
                # Apply trim if needed
                if scene.media.start_time is not None or scene.media.end_time is not None:
                    trim_params = {}
                    if scene.media.start_time is not None:
                        trim_params['start'] = scene.media.start_time
                    if scene.media.end_time is not None:
                        trim_params['end'] = scene.media.end_time
                    video_stream = video_stream.filter('trim', **trim_params)
                    video_stream = video_stream.filter('setpts', 'PTS-STARTPTS')
                
                # Apply duration if specified
                if scene.duration is not None:
                    video_stream = video_stream.filter('trim', duration=scene.duration)
                    video_stream = video_stream.filter('setpts', 'PTS-STARTPTS')
                
                # Resize to target resolution
                video_stream = video_stream.filter('scale', 
                                                  compose_request.settings.width, 
                                                  compose_request.settings.height)
                
                # Apply video effects
                if scene.media.effects:
                    video_stream = self._apply_video_effects(video_stream, scene.media.effects)
                
                # Apply text overlays
                if scene.text_overlays:
                    video_size = (compose_request.settings.width, compose_request.settings.height)
                    for text_overlay in scene.text_overlays:
                        video_stream = self._apply_text_overlay(video_stream, text_overlay, video_size)
                
                video_streams.append(video_stream)
                
                # Handle audio - check if media has audio based on file extension
                file_extension = file_path.lower().split('.')[-1]
                has_audio = file_extension in ['mp4', 'avi', 'mov', 'mkv', 'mp3', 'wav', 'aac', 'flac', 'm4a']
                
                if has_audio:
                    try:
                        audio_stream = input_stream.audio
                    except Exception as e:
                        logger.warning(f"Expected audio in {file_path} but none found, creating silent audio")
                        duration = scene.duration if scene.duration else 5.0
                        audio_stream = ffmpeg.input('anullsrc=channel_layout=stereo:sample_rate=48000', f='lavfi', t=duration).audio
                else:
                    logger.info(f"No audio expected for {file_path}, creating silent audio")
                    duration = scene.duration if scene.duration else 5.0
                    audio_stream = ffmpeg.input('anullsrc=channel_layout=stereo:sample_rate=48000', f='lavfi', t=duration).audio
                
                # Apply same timing constraints to audio
                audio_needs_pts_reset = False
                
                if scene.media.start_time is not None or scene.media.end_time is not None:
                    atrim_params = {}
                    if scene.media.start_time is not None:
                        atrim_params['start'] = scene.media.start_time
                    if scene.media.end_time is not None:
                        atrim_params['end'] = scene.media.end_time
                    audio_stream = audio_stream.filter('atrim', **atrim_params)
                    audio_needs_pts_reset = True
                
                if scene.duration is not None:
                    audio_stream = audio_stream.filter('atrim', duration=scene.duration)
                    audio_needs_pts_reset = True
                
                # Apply asetpts only once if needed with unique identifier
                if audio_needs_pts_reset:
                    # Add unique identifier to avoid filter conflicts
                    unique_adjustment = 1.0 + (index * 0.0001)  # Minimal volume adjustment for uniqueness
                    audio_stream = audio_stream.filter('asetpts', 'PTS-STARTPTS')
                    audio_stream = audio_stream.filter('volume', unique_adjustment)
                    # Ensure proper stream separation to avoid multiple outgoing edges
                    audio_stream = audio_stream.filter('anull')
                
                # Apply scene audio settings
                if scene.audio:
                    try:
                        scene_audio_path = self.get_file_path(scene.audio.file_id)
                        scene_audio_stream = ffmpeg.input(scene_audio_path).audio
                        
                        # Apply volume
                        if scene.audio.volume != 1.0:
                            scene_audio_stream = scene_audio_stream.filter('volume', scene.audio.volume)
                        
                        # Apply fade in/out
                        if scene.audio.fade_in:
                            scene_audio_stream = scene_audio_stream.filter('afade', type='in', duration=scene.audio.fade_in)
                        if scene.audio.fade_out:
                            scene_audio_stream = scene_audio_stream.filter('afade', type='out', duration=scene.audio.fade_out)
                        
                        # Mix with original audio
                        audio_stream = ffmpeg.filter([audio_stream, scene_audio_stream], 'amix')
                    except Exception as e:
                        logger.warning(f"Failed to add scene audio: {e}")

                # Handle voiceover
                if scene.voiceover:
                    try:
                        voiceover_path = self.get_file_path(scene.voiceover.file_id)
                        logger.info(f"Adding voiceover from: {voiceover_path}")
                        # Create a fresh input for each scene to avoid filter conflicts
                        voiceover_input = ffmpeg.input(voiceover_path)
                        voiceover_stream = voiceover_input.audio
                        
                        # Add a unique pass-through filter to ensure stream uniqueness
                        unique_id = f"scene_{index}_voiceover"
                        voiceover_stream = voiceover_stream.filter('anull')

                        # Apply volume
                        if scene.voiceover.volume != 1.0:
                            voiceover_stream = voiceover_stream.filter('volume', scene.voiceover.volume)

                        # Apply timing constraints
                        voiceover_needs_pts_reset = False
                        
                        if scene.voiceover.start_time is not None:
                            delay_ms = int(scene.voiceover.start_time * 1000)
                            voiceover_stream = voiceover_stream.filter('adelay', delays=f'{delay_ms}|{delay_ms}')
                            
                        if scene.voiceover.duration is not None:
                            voiceover_stream = voiceover_stream.filter('atrim', duration=scene.voiceover.duration)
                            voiceover_needs_pts_reset = True
                        
                        # Apply asetpts only once if needed with unique label
                        if voiceover_needs_pts_reset:
                            # Add a unique volume adjustment to create distinct filter paths
                            unique_vol = 1.0 + (index * 0.0001)  # Tiny volume difference to create unique paths
                            voiceover_stream = voiceover_stream.filter('asetpts', 'PTS-STARTPTS')
                            voiceover_stream = voiceover_stream.filter('volume', unique_vol)
                            # Ensure proper stream separation to avoid multiple outgoing edges
                            voiceover_stream = voiceover_stream.filter('anull')

                        # Check if original audio exists before mixing
                        if audio_stream is not None:
                            # Mix with original audio
                            audio_stream = ffmpeg.filter([audio_stream, voiceover_stream], 'amix', inputs=2, duration='longest')
                        else:
                            # No original audio, use voiceover as main audio
                            audio_stream = voiceover_stream
                            
                        logger.info(f"Successfully added voiceover for scene {scene.id}")
                    except Exception as e:
                        logger.warning(f"Failed to add voiceover for scene {scene.id}: {e}")

                audio_streams.append(audio_stream)

            self._update_progress(job_id, 50, "processing", "Applying transitions")

            # Apply transitions if specified
            if compose_request.transitions:
                final_video = self._apply_transitions(video_streams, compose_request.transitions)
                # For audio, ensure proper stream handling for concatenation
                if len(audio_streams) > 1:
                    # Filter out None streams
                    valid_audio_streams = [stream for stream in audio_streams if stream is not None]
                    if len(valid_audio_streams) > 1:
                        # Add asplit filters if needed to handle multiple outgoing edges
                        processed_streams = []
                        for i, stream in enumerate(valid_audio_streams):
                            # Ensure each stream has a unique identity for concatenation
                            stream = stream.filter('anull')
                            processed_streams.append(stream)
                        final_audio = ffmpeg.concat(*processed_streams, v=0, a=1)
                    elif len(valid_audio_streams) == 1:
                        final_audio = valid_audio_streams[0]
                    else:
                        # Create silent audio if no valid streams
                        final_audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi').audio
                else:
                    final_audio = audio_streams[0] if len(audio_streams) > 0 and audio_streams[0] is not None else ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi').audio
            else:
                # Simple concatenation
                if len(video_streams) > 1:
                    final_video = ffmpeg.concat(*video_streams, v=1, a=0)
                    # Handle audio concatenation with proper stream separation
                    valid_audio_streams = [stream for stream in audio_streams if stream is not None]
                    if len(valid_audio_streams) > 1:
                        # Add anull filter to ensure proper stream separation
                        processed_streams = []
                        for i, stream in enumerate(valid_audio_streams):
                            stream = stream.filter('anull')
                            processed_streams.append(stream)
                        final_audio = ffmpeg.concat(*processed_streams, v=0, a=1)
                    elif len(valid_audio_streams) == 1:
                        final_audio = valid_audio_streams[0]
                    else:
                        # Create silent audio if no valid streams
                        final_audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi').audio
                else:
                    final_video = video_streams[0]
                    final_audio = audio_streams[0] if len(audio_streams) > 0 and audio_streams[0] is not None else ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi').audio
            
            self._update_progress(job_id, 70, "processing", "Adding background music")
            
            # Add background music
            if compose_request.global_audio and compose_request.global_audio.background_music:
                try:
                    music = compose_request.global_audio.background_music
                    music_path = self.get_file_path(music.music_ID)
                    background_audio = ffmpeg.input(music_path).audio
                    
                    # Apply volume
                    background_audio = background_audio.filter('volume', music.volume)
                    
                    # Apply fade effects
                    if music.fade_in:
                        background_audio = background_audio.filter('afade', type='in', duration=music.fade_in)
                    if music.fade_out:
                        background_audio = background_audio.filter('afade', type='out', duration=music.fade_out)
                    
                    # Ensure proper stream isolation for mixing
                    background_audio = background_audio.filter('anull')
                    final_audio = final_audio.filter('anull')
                    
                    # Mix with existing audio using amix filter
                    final_audio = ffmpeg.filter([final_audio, background_audio], 'amix', inputs=2)
                    
                except Exception as e:
                    logger.warning(f"Failed to add background music: {e}")
            
            self._update_progress(job_id, 90, "processing", "Rendering final video")
            
            # Set quality parameters based on settings
            output_params = {
                'vcodec': 'libx264',
                'acodec': 'aac',
                'r': compose_request.settings.fps
            }
            
            if compose_request.settings.quality == "high":
                output_params['crf'] = 18
                output_params['preset'] = 'slow'
            elif compose_request.settings.quality == "medium":
                output_params['crf'] = 23
                output_params['preset'] = 'medium'
            else:  # low
                output_params['crf'] = 28
                output_params['preset'] = 'fast'
            
            # Render final video
            try:
                out, err = (ffmpeg
                 .output(final_video, final_audio, str(output_file), **output_params)
                 .overwrite_output()
                 .run(capture_stdout=True, capture_stderr=True)
                )
                logger.info(f"FFmpeg completed successfully")
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg error: {e}")
                logger.error(f"FFmpeg stdout: {e.stdout.decode() if e.stdout else 'No stdout'}")
                logger.error(f"FFmpeg stderr: {e.stderr.decode() if e.stderr else 'No stderr'}")
                raise
            
            self._update_progress(job_id, 100, "completed", "Video composition completed successfully")
            logger.info(f"Video composition completed: {output_file}")
            
        except Exception as e:
            error_msg = f"Video composition failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._update_progress(job_id, 0, "failed", error_msg)
            raise

# Global processor instance
video_processor = VideoProcessor()
