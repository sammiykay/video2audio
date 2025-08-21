"""Core FFmpeg wrapper and audio conversion functionality."""

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class FFmpegNotFoundError(Exception):
    """Raised when FFmpeg is not found on the system."""

    def __init__(self, message: str = "FFmpeg not found in PATH") -> None:
        self.message = message
        super().__init__(self.message)


class ConversionError(Exception):
    """Raised when conversion fails."""

    def __init__(self, message: str, returncode: Optional[int] = None) -> None:
        self.message = message
        self.returncode = returncode
        super().__init__(self.message)


@dataclass
class ConversionParams:
    """Parameters for audio conversion."""

    output_format: str = "mp3"
    codec: str = "libmp3lame"
    bitrate: str = "192k"
    sample_rate: int = 44100
    channels: int = 2
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    stream_index: Optional[int] = None
    normalize_loudness: bool = False
    normalize_peak: bool = False
    peak_target: float = -1.0


@dataclass
class MediaInfo:
    """Media file information."""

    duration: float
    streams: List[Dict[str, Any]]
    format_info: Dict[str, Any]
    metadata: Dict[str, str]


class AudioConverter:
    """Core audio conversion functionality using FFmpeg."""

    SUPPORTED_VIDEO_FORMATS = {
        ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp"
    }
    
    SUPPORTED_AUDIO_FORMATS = {
        ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma"
    }

    CODEC_MAP = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le", 
        "m4a": "aac",
        "flac": "flac",
        "aac": "aac",
        "ogg": "libvorbis",
    }

    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        """Initialize converter with optional FFmpeg path."""
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        if not self._check_ffmpeg():
            raise FFmpegNotFoundError()

    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable in PATH."""
        import shutil
        import os
        
        # Try common FFmpeg executable names
        ffmpeg_names = ["ffmpeg.exe", "ffmpeg"] if os.name == 'nt' else ["ffmpeg"]
        
        for name in ffmpeg_names:
            path = shutil.which(name)
            if path:
                return path
        
        # Try common installation paths by platform
        if os.name == 'nt':  # Windows
            common_paths = [
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe", 
                "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
                os.path.expanduser("~\\ffmpeg\\bin\\ffmpeg.exe"),
                os.path.expanduser("~\\scoop\\apps\\ffmpeg\\current\\bin\\ffmpeg.exe"),
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg*\\bin\\ffmpeg.exe"),
            ]
            for path in common_paths:
                if os.path.isfile(path):
                    return path
        
        elif os.name == 'posix':  # macOS and Linux
            import platform
            system = platform.system()
            
            if system == 'Darwin':  # macOS
                macos_paths = [
                    "/usr/local/bin/ffmpeg",
                    "/opt/homebrew/bin/ffmpeg",  # Apple Silicon Macs
                    "/usr/bin/ffmpeg",
                    os.path.expanduser("~/bin/ffmpeg"),
                    "/Applications/ffmpeg",
                ]
                for path in macos_paths:
                    if os.path.isfile(path):
                        return path
            
            else:  # Linux
                linux_paths = [
                    "/usr/bin/ffmpeg",
                    "/usr/local/bin/ffmpeg",
                    "/snap/bin/ffmpeg",  # Snap packages
                    "/var/lib/flatpak/exports/bin/org.ffmpeg.FFmpeg",  # Flatpak
                    os.path.expanduser("~/.local/bin/ffmpeg"),
                    os.path.expanduser("~/bin/ffmpeg"),
                ]
                for path in linux_paths:
                    if os.path.isfile(path):
                        return path
        
        return "ffmpeg"

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available and working."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_media_info(self, input_path: Path) -> MediaInfo:
        """Get media file information using ffprobe."""
        import os
        
        # Handle Windows paths properly
        if os.name == 'nt':
            if self.ffmpeg_path.endswith('ffmpeg.exe'):
                ffprobe_path = self.ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe')
            else:
                ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
        else:
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
        
        cmd = [
            ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(input_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise ConversionError(f"Failed to get media info: {result.stderr}")
                
            data = json.loads(result.stdout)
            
            # Extract duration
            duration = 0.0
            if "format" in data and "duration" in data["format"]:
                duration = float(data["format"]["duration"])
            
            # Extract streams
            streams = data.get("streams", [])
            
            # Extract format info
            format_info = data.get("format", {})
            
            # Extract metadata
            metadata = format_info.get("tags", {})
            
            return MediaInfo(
                duration=duration,
                streams=streams,
                format_info=format_info,
                metadata=metadata
            )
            
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError) as e:
            raise ConversionError(f"Failed to analyze media file: {str(e)}")

    def build_command(
        self, 
        input_path: Path, 
        output_path: Path, 
        params: ConversionParams
    ) -> List[str]:
        """Build FFmpeg command for conversion."""
        cmd = [self.ffmpeg_path, "-y", "-i", str(input_path)]
        
        # Time trimming
        if params.start_time:
            cmd.extend(["-ss", params.start_time])
        if params.end_time:
            cmd.extend(["-to", params.end_time])
        
        # Audio stream selection
        if params.stream_index is not None:
            cmd.extend(["-map", f"0:a:{params.stream_index}"])
        else:
            cmd.extend(["-map", "0:a:0"])  # First audio stream
        
        # Audio encoding parameters
        cmd.extend(["-c:a", params.codec])
        
        # Use high quality settings to preserve audio quality
        if params.codec == "libmp3lame":
            # Use VBR (Variable Bit Rate) for better quality
            cmd.extend(["-q:a", "0"])  # Highest quality VBR
            cmd.extend(["-b:a", params.bitrate])  # Still respect user bitrate choice
        else:
            cmd.extend(["-b:a", params.bitrate])
            
        cmd.extend(["-ar", str(params.sample_rate)])
        cmd.extend(["-ac", str(params.channels)])
        
        # Audio filters
        filters = []
        
        if params.normalize_loudness:
            # EBU R128 loudness normalization (less aggressive)
            filters.append("loudnorm=I=-18:LRA=7:TP=-2")
        elif params.normalize_peak:
            # Peak normalization
            filters.append(f"volume={params.peak_target}dB")
        
        # Don't apply any normalization by default to preserve original volume
        if filters:
            cmd.extend(["-af", ",".join(filters)])
        
        # Metadata preservation
        cmd.extend(["-map_metadata", "0"])
        
        # Output
        cmd.append(str(output_path))
        
        return cmd

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        params: ConversionParams,
        progress_callback: Optional[callable] = None
    ) -> None:
        """Convert video to audio with progress reporting."""
        logger.info(f"Converting {input_path} to {output_path}")
        
        # Get media info for progress calculation
        try:
            media_info = self.get_media_info(input_path)
            total_duration = media_info.duration
        except ConversionError:
            total_duration = 0.0
        
        cmd = self.build_command(input_path, output_path, params)
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Monitor progress
            progress_pattern = re.compile(
                r"time=(\d{2}):(\d{2}):(\d{2}\.?\d*)"
            )
            
            stderr_lines = []
            if process.stderr:
                for line in process.stderr:
                    stderr_lines.append(line.strip())
                    
                    # Parse progress
                    if progress_callback and total_duration > 0:
                        match = progress_pattern.search(line)
                        if match:
                            hours = int(match.group(1))
                            minutes = int(match.group(2))
                            seconds = float(match.group(3))
                            current_time = hours * 3600 + minutes * 60 + seconds
                            progress = min(current_time / total_duration, 1.0)
                            progress_callback(progress)
            
            process.wait()
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines[-10:])  # Last 10 lines
                raise ConversionError(
                    f"FFmpeg conversion failed: {error_msg}",
                    process.returncode
                )
                
        except subprocess.SubprocessError as e:
            raise ConversionError(f"Failed to start conversion: {str(e)}")

    def validate_time_format(self, time_str: str) -> bool:
        """Validate time format (HH:MM:SS or HH:MM:SS.mmm)."""
        pattern = r"^\d{1,2}:\d{2}:\d{2}(\.\d{1,3})?$"
        return bool(re.match(pattern, time_str))

    def time_to_seconds(self, time_str: str) -> float:
        """Convert time string to seconds."""
        if not self.validate_time_format(time_str):
            raise ValueError(f"Invalid time format: {time_str}")
        
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        
        return hours * 3600 + minutes * 60 + seconds

    def get_audio_streams(self, input_path: Path) -> List[Dict[str, Any]]:
        """Get audio stream information from media file."""
        media_info = self.get_media_info(input_path)
        return [
            stream for stream in media_info.streams
            if stream.get("codec_type") == "audio"
        ]

    def extract_metadata(self, input_path: Path) -> Dict[str, str]:
        """Extract metadata that can be copied to output file."""
        media_info = self.get_media_info(input_path)
        metadata = media_info.metadata
        
        # Clean up metadata keys for audio files
        audio_metadata = {}
        key_map = {
            "title": "title",
            "artist": "artist", 
            "album": "album",
            "date": "date",
            "genre": "genre",
            "track": "track",
            "albumartist": "album_artist",
            "composer": "composer",
            "comment": "comment",
        }
        
        for orig_key, new_key in key_map.items():
            if orig_key in metadata:
                audio_metadata[new_key] = metadata[orig_key]
        
        return audio_metadata

    @classmethod
    def is_supported_format(cls, file_path: Path) -> bool:
        """Check if file format is supported for conversion."""
        suffix = file_path.suffix.lower()
        return (
            suffix in cls.SUPPORTED_VIDEO_FORMATS or
            suffix in cls.SUPPORTED_AUDIO_FORMATS
        )

    @classmethod
    def get_default_codec(cls, output_format: str) -> str:
        """Get default codec for output format."""
        return cls.CODEC_MAP.get(output_format.lower(), "libmp3lame")