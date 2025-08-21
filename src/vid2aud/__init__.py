"""Video to Audio Converter - A cross-platform GUI application for batch video to audio conversion."""

__version__ = "1.0.0"
__author__ = "Video Converter Team"
__email__ = "team@vid2aud.com"

from .converter import AudioConverter, ConversionError, FFmpegNotFoundError
from .settings import Settings
from .fsutils import ValidationError

__all__ = [
    "AudioConverter",
    "ConversionError", 
    "FFmpegNotFoundError",
    "ValidationError",
    "Settings",
]