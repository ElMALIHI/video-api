import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from moviepy.editor import *
from moviepy.config import check
import json
from datetime import datetime

from app.models import CompositionRequest, Scene, Transition, TextOverlay, Position

logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
TEMP_DIR = os.getenv("TEMP_DIR", "./temp")

class VideoProcessor:
    """
    Video processor that handles video composition using MoviePy.
    """
    
    def __init__(self):
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [OUTPUT_DIR, TEMP_DIR]:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
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
    
    def create_text_clip(self, text_overlay: TextOverlay, video_size: Tuple[int, int], scene_duration: float) -> TextClip:
        """
        Create a text clip from text overlay specification.
        
        Args:
            text_overlay: Text overlay configuration
            video_size: Video dimensions
            scene_duration: Duration of the scene
            
        Returns:
            TextClip: MoviePy text clip
        """
        # Convert position
        x, y = self.convert_position(text_overlay.position, video_size)
        
        # Determine text duration
        if text_overlay.duration:
            duration = text_overlay.duration
        else:
            duration = scene_duration
        
        # Create text clip
        txt_clip = TextClip(
            text_overlay.text,
            fontsize=text_overlay.font_size,
            color=text_overlay.color,
            font='Arial',  # You might want to make this configurable
            stroke_color=text_overlay.background_color if text_overlay.background_color else None,
            stroke_width=2 if text_overlay.background_color else 0
        ).set_duration(duration).set_position((x, y))
        
        # Set start time if specified
        if text_overlay.start_time:
            txt_clip = txt_clip.set_start(text_overlay.start_time)
        
        return txt_clip
    
    def process_scene(self, scene: Scene, video_settings: Dict, scene_index: int) -> VideoFileClip:
        """
        Process a single scene.
        
        Args:
            scene: Scene configuration
            video_settings: Video settings from composition request
            scene_index: Index of the scene
            
        Returns:
            VideoFileClip: Processed scene clip
        """
        logger.info(f"Processing scene {scene.id} (index {scene_index})")
        
        # Get media file path
        media_path = self.get_file_path(scene.media.file_id)
        
        # Load media based on type
        if scene.media.type == "image":
            # Create image clip
            clip = ImageClip(media_path)
            
            # Set duration - use scene duration or default to 5 seconds
            duration = scene.duration if scene.duration else 5.0
            clip = clip.set_duration(duration)
            
        elif scene.media.type == "video":
            # Load video clip
            clip = VideoFileClip(media_path)
            
            # Apply start/end time if specified
            if scene.media.start_time is not None:
                if scene.media.end_time is not None:
                    clip = clip.subclip(scene.media.start_time, scene.media.end_time)
                else:
                    clip = clip.subclip(scene.media.start_time)
            elif scene.media.end_time is not None:
                clip = clip.subclip(0, scene.media.end_time)
            
            # Apply scene duration if specified
            if scene.duration:
                clip = clip.set_duration(scene.duration)
        
        else:
            raise ValueError(f"Unsupported media type: {scene.media.type}")
        
        # Resize to target resolution
        target_size = (video_settings['width'], video_settings['height'])
        clip = clip.resize(target_size)
        
        # Apply media effects
        if scene.media.effects:
            effects = scene.media.effects
            
            if effects.zoom and effects.zoom != 1.0:
                clip = clip.resize(effects.zoom)
            
            if effects.speed and effects.speed != 1.0:
                clip = clip.fx(speedx, effects.speed)
            
            if effects.brightness and effects.brightness != 1.0:
                clip = clip.fx(colorx, effects.brightness)
        
        # Add text overlays
        clips_to_composite = [clip]
        
        if scene.text_overlays:
            for text_overlay in scene.text_overlays:
                txt_clip = self.create_text_clip(text_overlay, target_size, clip.duration)
                clips_to_composite.append(txt_clip)
        
        # Add scene audio if specified
        if scene.audio:
            try:
                audio_path = self.get_file_path(scene.audio.file_id)
                audio_clip = AudioFileClip(audio_path)
                
                # Apply audio settings
                if scene.audio.volume != 1.0:
                    audio_clip = audio_clip.volumex(scene.audio.volume)
                
                # Apply fade in/out
                if scene.audio.fade_in:
                    audio_clip = audio_clip.audio_fadein(scene.audio.fade_in)
                if scene.audio.fade_out:
                    audio_clip = audio_clip.audio_fadeout(scene.audio.fade_out)
                
                # Set audio duration to match clip
                audio_clip = audio_clip.set_duration(clip.duration)
                
                # Composite the clips
                if len(clips_to_composite) > 1:
                    final_clip = CompositeVideoClip(clips_to_composite)
                else:
                    final_clip = clip
                
                final_clip = final_clip.set_audio(audio_clip)
                
            except Exception as e:
                logger.warning(f"Failed to add audio to scene {scene.id}: {str(e)}")
                final_clip = CompositeVideoClip(clips_to_composite) if len(clips_to_composite) > 1 else clip
        else:
            final_clip = CompositeVideoClip(clips_to_composite) if len(clips_to_composite) > 1 else clip
        
        logger.info(f"Scene {scene.id} processed successfully, duration: {final_clip.duration}s")
        return final_clip
    
    def apply_transition(self, clip1: VideoFileClip, clip2: VideoFileClip, transition: Transition) -> VideoFileClip:
        """
        Apply transition between two clips.
        
        Args:
            clip1: First clip
            clip2: Second clip  
            transition: Transition configuration
            
        Returns:
            VideoFileClip: Clips with transition applied
        """
        logger.info(f"Applying {transition.type} transition ({transition.duration}s)")
        
        if transition.type == "fade":
            # Fade out first clip and fade in second clip
            clip1_with_fadeout = clip1.fadeout(transition.duration)
            clip2_with_fadein = clip2.fadein(transition.duration)
            
            # Overlap the clips during transition
            clip2_with_fadein = clip2_with_fadein.set_start(clip1.duration - transition.duration)
            
            return concatenate_videoclips([clip1_with_fadeout, clip2_with_fadein])
        
        elif transition.type in ["slide_left", "slide_right", "slide_up", "slide_down"]:
            # For slides, we'll use a simple crossfade for now
            # In a full implementation, you'd implement actual sliding effects
            logger.warning(f"Slide transitions not fully implemented, using crossfade")
            return concatenate_videoclips([clip1, clip2], method="compose")
        
        else:
            # Default: simple concatenation
            logger.warning(f"Transition type {transition.type} not implemented, using simple cut")
            return concatenate_videoclips([clip1, clip2])
    
    def process_composition(self, request: CompositionRequest, job_id: int, progress_callback=None) -> str:
        """
        Process the complete video composition.
        
        Args:
            request: Video composition request
            job_id: Job identifier for output filename
            progress_callback: Optional callback for progress updates
            
        Returns:
            str: Path to output video file
        """
        logger.info(f"Starting video composition for job {job_id}")
        
        if progress_callback:
            progress_callback(10, "Processing scenes...")
        
        # Process all scenes
        scene_clips = []
        video_settings = {
            'width': request.settings.width,
            'height': request.settings.height,
            'fps': request.settings.fps
        }
        
        for i, scene in enumerate(request.scenes):
            try:
                clip = self.process_scene(scene, video_settings, i)
                scene_clips.append(clip)
                
                if progress_callback:
                    progress = 10 + (i + 1) * 40 / len(request.scenes)
                    progress_callback(progress, f"Processed scene {i + 1}/{len(request.scenes)}")
                    
            except Exception as e:
                logger.error(f"Failed to process scene {scene.id}: {str(e)}")
                raise
        
        if progress_callback:
            progress_callback(50, "Applying transitions...")
        
        # Apply transitions
        if request.transitions and len(scene_clips) > 1:
            # Build a map of transitions
            transition_map = {(t.from_scene, t.to_scene): t for t in request.transitions}
            
            final_clips = [scene_clips[0]]
            
            for i in range(1, len(scene_clips)):
                from_scene = request.scenes[i-1].id
                to_scene = request.scenes[i].id
                
                if (from_scene, to_scene) in transition_map:
                    transition = transition_map[(from_scene, to_scene)]
                    # For now, just concatenate with a simple crossfade
                    # In a full implementation, you'd apply the specific transition
                    final_clips.append(scene_clips[i])
                else:
                    final_clips.append(scene_clips[i])
            
            final_video = concatenate_videoclips(final_clips)
        else:
            final_video = concatenate_videoclips(scene_clips)
        
        if progress_callback:
            progress_callback(70, "Adding background music...")
        
        # Add background music if specified
        if request.global_audio and request.global_audio.background_music:
            try:
                music = request.global_audio.background_music
                music_path = self.get_file_path(music.music_ID)
                background_audio = AudioFileClip(music_path)
                
                # Apply volume
                background_audio = background_audio.volumex(music.volume)
                
                # Loop if necessary
                if music.loop and background_audio.duration < final_video.duration:
                    background_audio = background_audio.loop(duration=final_video.duration)
                else:
                    background_audio = background_audio.set_duration(final_video.duration)
                
                # Apply fade in/out
                if music.fade_in:
                    background_audio = background_audio.audio_fadein(music.fade_in)
                if music.fade_out:
                    background_audio = background_audio.audio_fadeout(music.fade_out)
                
                # Composite with existing audio
                if final_video.audio:
                    final_audio = CompositeAudioClip([final_video.audio, background_audio])
                else:
                    final_audio = background_audio
                
                final_video = final_video.set_audio(final_audio)
                
            except Exception as e:
                logger.warning(f"Failed to add background music: {str(e)}")
        
        if progress_callback:
            progress_callback(80, "Finalizing video...")
        
        # Set final video properties
        final_video = final_video.set_fps(request.settings.fps)
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"video_job_{job_id}_{timestamp}.{request.output.format}"
        output_path = Path(OUTPUT_DIR) / output_filename
        
        if progress_callback:
            progress_callback(90, "Rendering video...")
        
        # Write video file
        codec = request.output.codec if request.output.codec == "h264" else "libx264"
        
        # Quality settings
        if request.settings.quality == "high":
            bitrate = "5000k"
        elif request.settings.quality == "medium":
            bitrate = "2500k"
        else:
            bitrate = "1000k"
        
        final_video.write_videofile(
            str(output_path),
            codec=codec,
            bitrate=bitrate,
            temp_audiofile_path=str(Path(TEMP_DIR) / f"temp_audio_{job_id}.m4a"),
            remove_temp=True,
            verbose=False,
            logger=None  # Disable moviepy logging to avoid conflicts
        )
        
        # Cleanup
        final_video.close()
        for clip in scene_clips:
            clip.close()
        
        if progress_callback:
            progress_callback(100, "Video composition completed!")
        
        logger.info(f"Video composition completed: {output_path}")
        return str(output_path)

# Global processor instance
video_processor = VideoProcessor()
