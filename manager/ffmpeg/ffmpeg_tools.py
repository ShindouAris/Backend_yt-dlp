import ffmpeg
import subprocess
import os
from logging import getLogger

log = getLogger(__name__)

class FFmpegTools:
    """Class to handle merging audio into video files using FFmpeg"""
    
    def __init__(self):
        self.check_ffmpeg()
        self.has_ffmpeg = True

    def check_ffmpeg(self):
        """Check if FFmpeg is installed"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            log.info("✓ FFmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.warning("✗ FFmpeg is not installed or not found in PATH")
            self.has_ffmpeg = False
            raise RuntimeError("FFmpeg not found. Please install FFmpeg first.")
    
    def merge_audio(self, video_path, audio_path, output_path, 
                                replace_audio=True, audio_codec='aac'):
        """
        Merge audio into video using ffmpeg-python library
        
        Args:
            video_path: Path to input video file
            audio_path: Path to input audio file  
            output_path: Path for output file
            replace_audio: If True, replace existing audio. If False, mix with existing
            audio_codec: Audio codec to use (aac, mp3, etc.)
        """
        if not self.has_ffmpeg:
            log.error("FFmpeg is not available. Cannot perform merge operation.")
            return False
        try:
            # Validate input files
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Input streams
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            if replace_audio:
                # Replace existing audio completely
                output = ffmpeg.output(
                    video_input.video,     # video stream only
                    audio_input.audio,     # audio stream only
                    output_path,
                    vcodec='copy',         # copy video without re-encoding
                    acodec=audio_codec
                )
            else:
                # Mix new audio with existing audio
                # Get existing audio from video
                video_audio = video_input.audio
                
                # Mix the two audio streams
                mixed_audio = ffmpeg.filter([video_audio, audio_input], 'amix', 
                                          inputs=2, duration='shortest')
                
                output = ffmpeg.output(
                    video_input.video,
                    mixed_audio,
                    output_path,
                    vcodec='copy',
                    acodec=audio_codec
                )
            
            # Run the FFmpeg command with error handling
            log.info(f"Processing: {video_path} + {audio_path} -> {output_path}")
            ffmpeg.run(output, overwrite_output=True, quiet=False)
            log.info(f"✓ Successfully merged audio into video: {output_path}")
            return True
        except ffmpeg.Error as e:
            log.error(f"✗ FFmpeg error: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                log.error(f"Error details: {e.stderr.decode()}")
            return False
        except FileNotFoundError as e:
            log.error(f"✗ File error: {e}")
            return False
        except Exception as e:
            log.error(f"✗ Unexpected error: {e}")
            return False
    

    def adjust_audio_sync(self, video_path, audio_path, output_path, 
                         audio_delay=0.0, audio_codec='aac'):
        """
        Merge audio with video and adjust sync (delay/advance audio)
        
        Args:
            video_path: Path to input video
            audio_path: Path to input audio
            output_path: Path for output
            audio_delay: Delay in seconds (positive = delay, negative = advance)
            audio_codec: Audio codec to use
        """
        if not self.has_ffmpeg:
            log.error("FFmpeg is not available. Cannot perform sync adjustment.")
            return
        try:
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            # Apply audio delay if specified
            if audio_delay != 0:
                audio_input = ffmpeg.filter(audio_input, 'adelay', f'{int(audio_delay * 1000)}')
            
            output = ffmpeg.output(
                video_input.video,
                audio_input,
                output_path,
                vcodec='copy',
                acodec=audio_codec
            )
            
            ffmpeg.run(output, overwrite_output=True)
            log.info(f"✓ Merged with {audio_delay}s audio delay: {output_path}")
            
        except Exception as e:
            log.error(f"✗ Error adjusting sync: {e}")

    def add_subtitle_as_selectable_track(self, video_path, subtitle_path, output_path):
        """
        Add subtitle to video using ffmpeg-python library as a selectable subtitle track
        
        Args:
            video_path: Path to input video file
            subtitle_path: Path to input subtitle file
            output_path: Path for output file
        """
        if not self.has_ffmpeg:
            log.error("FFmpeg is not available. Cannot add subtitle track.")
            return
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            if not os.path.exists(subtitle_path):
                raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
            
            video = ffmpeg.input(video_path)
            subtitle = ffmpeg.input(subtitle_path)
            
            output = ffmpeg.output(
                video,
                subtitle,
                output_path,
                map_metadata='-1', 
                vcodec='copy',     
                acodec='copy',    
                scodec='mov_text'  
            )

            ffmpeg.run(output, overwrite_output=True)
            log.info(f"✓ Successfully added selectable subtitle track to video: {output_path}")

        except Exception as e:
            log.error(f"✗ Error adding subtitle: {e}")

    def add_subtitle_as_burned_in_text(self, video_path, subtitle_path, output_path, preset='veryfast'):
        """
        Add subtitle to video using ffmpeg-python library as a burned-in text
        
        [WARING]: Slow and not recommended for large files
        
        Args:
            video_path: Path to input video file
            subtitle_path: Path to input subtitle file
            output_path: Path for output file
            preset: FFmpeg preset for encoding speed (options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
        """
        if not self.has_ffmpeg:
            log.error("FFmpeg is not available. Cannot add burned-in subtitle.")
            return
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            if not os.path.exists(subtitle_path):
                raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
            
            log.warning("⚠️ This operation is slow and not recommended for large files")
            log.warning("⚠️ Use add_subtitle_as_selectable_track for faster performance")
            log.warning("⚠️ This may take up to 10 minutes...")
            
            output = (
                ffmpeg
                .input(video_path)
                .output(output_path,
                        vf=f'subtitles={subtitle_path}', 
                        acodec='copy',
                        vcodec='h264',
                        preset=preset,  
                        crf=23      
                )
            )

            ffmpeg.run(output, overwrite_output=True)
            log.info(f"✓ Successfully added subtitle to video: {output_path}")

        except Exception as e:
            log.error(f"✗ Error adding subtitle: {e}")

