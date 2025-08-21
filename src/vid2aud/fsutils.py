"""Filesystem utilities for path handling, validation, and unique naming."""

import os
import re
from pathlib import Path
from typing import List, Optional, Set


class ValidationError(Exception):
    """Raised when file or path validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class PathUtils:
    """Utilities for path manipulation and validation."""

    INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename by removing invalid characters."""
        # Replace invalid characters with underscores
        sanitized = re.sub(cls.INVALID_FILENAME_CHARS, "_", filename)
        
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(". ")
        
        # Ensure filename is not empty
        if not sanitized:
            sanitized = "converted_file"
        
        # Truncate if too long
        if len(sanitized) > cls.MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(sanitized)
            max_name_len = cls.MAX_FILENAME_LENGTH - len(ext)
            sanitized = name[:max_name_len] + ext
        
        return sanitized

    @classmethod
    def validate_path(cls, path: Path) -> None:
        """Validate that path is safe and within reasonable limits."""
        path_str = str(path.resolve())
        
        if len(path_str) > cls.MAX_PATH_LENGTH:
            raise ValidationError(f"Path too long: {len(path_str)} > {cls.MAX_PATH_LENGTH}")
        
        # Check for problematic patterns
        if ".." in path.parts:
            raise ValidationError("Path contains '..' components")
        
        # Check if parent directory exists and is writable
        parent = path.parent
        if not parent.exists():
            raise ValidationError(f"Parent directory does not exist: {parent}")
        
        if not os.access(parent, os.W_OK):
            raise ValidationError(f"Parent directory is not writable: {parent}")

    @classmethod
    def get_unique_filename(
        cls, 
        directory: Path, 
        base_name: str, 
        extension: str
    ) -> Path:
        """Generate unique filename by appending numbers if file exists."""
        # Sanitize the base name
        base_name = cls.sanitize_filename(base_name)
        
        # Try the original name first
        candidate = directory / f"{base_name}{extension}"
        if not candidate.exists():
            return candidate
        
        # Generate numbered variants
        counter = 1
        while counter <= 9999:  # Reasonable limit
            candidate = directory / f"{base_name} ({counter}){extension}"
            if not candidate.exists():
                return candidate
            counter += 1
        
        raise ValidationError(f"Could not generate unique filename for {base_name}")

    @classmethod
    def is_safe_directory(cls, directory: Path) -> bool:
        """Check if directory is safe for operations (exists, writable, not system)."""
        if not directory.exists() or not directory.is_dir():
            return False
        
        if not os.access(directory, os.R_OK | os.W_OK):
            return False
        
        # Avoid system directories on Windows
        if os.name == "nt":
            system_dirs = {
                Path(os.environ.get("WINDIR", "C:\\Windows")).resolve(),
                Path("C:\\System32").resolve(),
                Path("C:\\Program Files").resolve(),
                Path("C:\\Program Files (x86)").resolve(),
            }
            resolved_dir = directory.resolve()
            for sys_dir in system_dirs:
                try:
                    resolved_dir.relative_to(sys_dir)
                    return False  # Directory is under system directory
                except ValueError:
                    continue  # Not under this system directory
        
        return True


class FileFilter:
    """File filtering utilities for batch operations."""

    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        supported_extensions: Optional[Set[str]] = None
    ) -> None:
        """Initialize file filter with patterns and extensions."""
        self.include_patterns = include_patterns or ["*"]
        self.exclude_patterns = exclude_patterns or []
        self.supported_extensions = supported_extensions or set()

    def matches_pattern(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename matches any of the patterns."""
        import fnmatch
        
        for pattern in patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if file is supported based on extension and patterns."""
        filename = file_path.name
        
        # Check extension if specified
        if self.supported_extensions:
            if file_path.suffix.lower() not in self.supported_extensions:
                return False
        
        # Check include patterns
        if not self.matches_pattern(filename, self.include_patterns):
            return False
        
        # Check exclude patterns
        if self.matches_pattern(filename, self.exclude_patterns):
            return False
        
        return True

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        follow_symlinks: bool = False
    ) -> List[Path]:
        """Scan directory for matching files."""
        if not directory.is_dir():
            raise ValidationError(f"Not a directory: {directory}")
        
        files = []
        
        try:
            if recursive:
                for root, dirs, filenames in os.walk(
                    directory, 
                    followlinks=follow_symlinks
                ):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    
                    root_path = Path(root)
                    for filename in filenames:
                        if filename.startswith("."):
                            continue  # Skip hidden files
                        
                        file_path = root_path / filename
                        if self.is_supported_file(file_path):
                            files.append(file_path)
            else:
                for file_path in directory.iterdir():
                    if file_path.is_file() and not file_path.name.startswith("."):
                        if self.is_supported_file(file_path):
                            files.append(file_path)
        
        except (OSError, PermissionError) as e:
            raise ValidationError(f"Failed to scan directory {directory}: {str(e)}")
        
        return sorted(files)


class OverwritePolicy:
    """Handle file overwrite policies."""

    SKIP = "skip"
    REPLACE = "replace"
    UNIQUE = "unique"

    @classmethod
    def resolve_output_path(
        cls,
        output_path: Path,
        policy: str = UNIQUE
    ) -> tuple[Path, bool]:
        """
        Resolve output path based on overwrite policy.
        
        Returns:
            Tuple of (resolved_path, should_skip)
        """
        if policy == cls.SKIP and output_path.exists():
            return output_path, True  # Skip this file
        
        elif policy == cls.REPLACE:
            return output_path, False  # Overwrite existing
        
        elif policy == cls.UNIQUE:
            if not output_path.exists():
                return output_path, False
            
            # Generate unique name
            directory = output_path.parent
            stem = output_path.stem
            suffix = output_path.suffix
            
            unique_path = PathUtils.get_unique_filename(directory, stem, suffix)
            return unique_path, False
        
        else:
            raise ValueError(f"Unknown overwrite policy: {policy}")


def get_safe_output_directory(input_path: Path, default_output: Optional[Path] = None) -> Path:
    """Get safe output directory for a given input file."""
    if default_output and PathUtils.is_safe_directory(default_output):
        return default_output
    
    # Fall back to input file's directory
    input_dir = input_path.parent
    if PathUtils.is_safe_directory(input_dir):
        return input_dir
    
    # Fall back to user's home directory
    home_dir = Path.home()
    if PathUtils.is_safe_directory(home_dir):
        return home_dir
    
    raise ValidationError("No safe output directory available")


def ensure_directory_exists(directory: Path) -> None:
    """Ensure directory exists, creating it if necessary."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise ValidationError(f"Failed to create directory {directory}: {str(e)}")


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes."""
    try:
        size_bytes = file_path.stat().st_size
        return size_bytes / (1024 * 1024)
    except (OSError, FileNotFoundError):
        return 0.0


def is_file_accessible(file_path: Path) -> bool:
    """Check if file is accessible for reading."""
    try:
        return file_path.exists() and os.access(file_path, os.R_OK)
    except (OSError, PermissionError):
        return False