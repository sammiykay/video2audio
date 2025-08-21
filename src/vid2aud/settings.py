"""Settings management with cross-platform storage using appdirs."""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import appdirs

logger = logging.getLogger(__name__)


@dataclass
class ConversionSettings:
    """Default conversion settings."""
    
    output_format: str = "mp3"
    codec: str = "libmp3lame"
    bitrate: str = "192k"
    sample_rate: int = 44100
    channels: int = 2
    normalize_loudness: bool = False
    normalize_peak: bool = False
    peak_target: float = 0.0  # No volume change by default


@dataclass
class UISettings:
    """User interface settings."""
    
    theme: str = "system"  # system, light, dark
    high_dpi_scaling: bool = True
    window_width: int = 1200
    window_height: int = 800
    window_maximized: bool = False
    splitter_sizes: list[int] = None
    table_column_widths: Dict[str, int] = None
    
    def __post_init__(self) -> None:
        """Initialize default values after dataclass creation."""
        if self.splitter_sizes is None:
            self.splitter_sizes = [600, 200]
        if self.table_column_widths is None:
            self.table_column_widths = {
                "source": 300,
                "target": 300,
                "status": 100,
                "progress": 100,
                "duration": 80,
                "eta": 80,
            }


@dataclass
class ProcessingSettings:
    """Processing and performance settings."""
    
    max_concurrent_jobs: int = 4
    retry_attempts: int = 3
    retry_backoff_base: float = 2.0
    overwrite_policy: str = "unique"  # skip, replace, unique
    watch_folders: bool = False
    auto_start_conversions: bool = False


@dataclass
class PathSettings:
    """File and directory path settings."""
    
    default_output_dir: str = ""
    use_source_directory: bool = True
    ffmpeg_path: str = ""
    last_input_dir: str = ""
    last_output_dir: str = ""


@dataclass
class Settings:
    """Application settings container."""
    
    conversion: ConversionSettings = None
    ui: UISettings = None
    processing: ProcessingSettings = None
    paths: PathSettings = None
    logging_level: str = "INFO"
    
    def __post_init__(self) -> None:
        """Initialize sub-settings if not provided."""
        if self.conversion is None:
            self.conversion = ConversionSettings()
        if self.ui is None:
            self.ui = UISettings()
        if self.processing is None:
            self.processing = ProcessingSettings()
        if self.paths is None:
            self.paths = PathSettings()


class SettingsManager:
    """Manages application settings with persistent storage."""
    
    APP_NAME = "Vid2Aud"
    APP_AUTHOR = "Vid2AudTeam"
    SETTINGS_FILENAME = "settings.json"
    
    def __init__(self) -> None:
        """Initialize settings manager."""
        self._config_dir = Path(appdirs.user_config_dir(self.APP_NAME, self.APP_AUTHOR))
        self._cache_dir = Path(appdirs.user_cache_dir(self.APP_NAME, self.APP_AUTHOR))
        self._log_dir = Path(appdirs.user_log_dir(self.APP_NAME, self.APP_AUTHOR))
        self._data_dir = Path(appdirs.user_data_dir(self.APP_NAME, self.APP_AUTHOR))
        
        self._settings_path = self._config_dir / self.SETTINGS_FILENAME
        self._settings: Optional[Settings] = None
        
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create application directories if they don't exist."""
        for directory in [self._config_dir, self._cache_dir, self._log_dir, self._data_dir]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Failed to create directory {directory}: {e}")
    
    @property
    def config_dir(self) -> Path:
        """Get configuration directory path."""
        return self._config_dir
    
    @property
    def cache_dir(self) -> Path:
        """Get cache directory path."""
        return self._cache_dir
    
    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        return self._log_dir
    
    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._data_dir
    
    def load_settings(self) -> Settings:
        """Load settings from file or return defaults."""
        if self._settings is not None:
            return self._settings
        
        if not self._settings_path.exists():
            logger.info("Settings file not found, using defaults")
            self._settings = Settings()
            return self._settings
        
        try:
            with open(self._settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._settings = self._deserialize_settings(data)
            logger.info(f"Loaded settings from {self._settings_path}")
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load settings: {e}, using defaults")
            self._settings = Settings()
        
        return self._settings
    
    def save_settings(self, settings: Optional[Settings] = None) -> None:
        """Save settings to file."""
        if settings is not None:
            self._settings = settings
        
        if self._settings is None:
            logger.warning("No settings to save")
            return
        
        try:
            data = self._serialize_settings(self._settings)
            
            # Create backup of existing settings
            if self._settings_path.exists():
                backup_path = self._settings_path.with_suffix(".json.bak")
                self._settings_path.replace(backup_path)
            
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved settings to {self._settings_path}")
            
        except (OSError, ValueError) as e:
            logger.error(f"Failed to save settings: {e}")
    
    def _serialize_settings(self, settings: Settings) -> Dict[str, Any]:
        """Convert settings to JSON-serializable dictionary."""
        return {
            "conversion": asdict(settings.conversion),
            "ui": asdict(settings.ui),
            "processing": asdict(settings.processing),
            "paths": asdict(settings.paths),
            "logging_level": settings.logging_level,
        }
    
    def _deserialize_settings(self, data: Dict[str, Any]) -> Settings:
        """Convert dictionary to Settings object."""
        conversion = ConversionSettings(**data.get("conversion", {}))
        ui_data = data.get("ui", {})
        ui = UISettings(**ui_data)
        processing = ProcessingSettings(**data.get("processing", {}))
        paths = PathSettings(**data.get("paths", {}))
        
        return Settings(
            conversion=conversion,
            ui=ui,
            processing=processing,
            paths=paths,
            logging_level=data.get("logging_level", "INFO"),
        )
    
    def get_session_file(self) -> Path:
        """Get path for session state file."""
        return self._data_dir / "session.json"
    
    def save_session_state(self, queue_items: list, window_state: Dict[str, Any]) -> None:
        """Save current session state for crash recovery."""
        session_data = {
            "queue_items": queue_items,
            "window_state": window_state,
            "timestamp": str(Path(__file__).stat().st_mtime),  # Use current time
        }
        
        try:
            with open(self.get_session_file(), "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, default=str)
            logger.debug("Saved session state")
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to save session state: {e}")
    
    def load_session_state(self) -> Optional[Dict[str, Any]]:
        """Load saved session state."""
        session_file = self.get_session_file()
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load session state: {e}")
            return None
    
    def clear_session_state(self) -> None:
        """Clear saved session state."""
        session_file = self.get_session_file()
        if session_file.exists():
            try:
                session_file.unlink()
                logger.debug("Cleared session state")
            except OSError as e:
                logger.warning(f"Failed to clear session state: {e}")
    
    def get_log_file_path(self) -> Path:
        """Get path for application log file."""
        return self._log_dir / "vid2aud.log"
    
    def setup_logging(self, level: Optional[str] = None) -> None:
        """Setup application logging configuration."""
        if level is None and self._settings:
            level = self._settings.logging_level
        
        log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
        
        # Create rotating file handler
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            self.get_log_file_path(),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        
        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        logger.info(f"Logging configured at {log_level} level")


# Global settings manager instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def get_settings() -> Settings:
    """Get current application settings."""
    return get_settings_manager().load_settings()


def save_settings(settings: Settings) -> None:
    """Save application settings."""
    get_settings_manager().save_settings(settings)