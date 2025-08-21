"""Dialog windows for settings, about, and FFmpeg help."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..settings import Settings

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings configuration dialog."""
    
    def __init__(self, settings: Settings, parent=None) -> None:
        """Initialize settings dialog."""
        super().__init__(parent)
        self.settings = settings.copy() if hasattr(settings, 'copy') else settings
        
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self._create_conversion_tab()
        self._create_processing_tab()
        self._create_paths_tab()
        self._create_interface_tab()
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_conversion_tab(self) -> None:
        """Create conversion settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Default format group
        format_group = QGroupBox("Default Format Settings")
        format_layout = QFormLayout(format_group)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "wav", "m4a", "flac"])
        format_layout.addRow("Output Format:", self.format_combo)
        
        self.bitrate_edit = QLineEdit()
        format_layout.addRow("Bitrate:", self.bitrate_edit)
        
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(8000, 192000)
        self.sample_rate_spin.setValue(44100)
        format_layout.addRow("Sample Rate:", self.sample_rate_spin)
        
        self.channels_spin = QSpinBox()
        self.channels_spin.setRange(1, 8)
        self.channels_spin.setValue(2)
        format_layout.addRow("Channels:", self.channels_spin)
        
        layout.addWidget(format_group)
        
        # Audio processing group
        processing_group = QGroupBox("Audio Processing")
        processing_layout = QFormLayout(processing_group)
        
        self.normalize_loudness_check = QCheckBox()
        processing_layout.addRow("Loudness Normalization:", self.normalize_loudness_check)
        
        self.normalize_peak_check = QCheckBox()
        processing_layout.addRow("Peak Normalization:", self.normalize_peak_check)
        
        self.peak_target_edit = QLineEdit()
        processing_layout.addRow("Peak Target (dB):", self.peak_target_edit)
        
        # Add note about volume preservation
        note_label = QLabel("Note: Leave normalization off to preserve original volume levels")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        processing_layout.addRow("", note_label)
        
        layout.addWidget(processing_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Conversion")
    
    def _create_processing_tab(self) -> None:
        """Create processing settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Performance group
        performance_group = QGroupBox("Performance")
        performance_layout = QFormLayout(performance_group)
        
        self.concurrent_jobs_spin = QSpinBox()
        self.concurrent_jobs_spin.setRange(1, 16)
        self.concurrent_jobs_spin.setValue(4)
        performance_layout.addRow("Concurrent Jobs:", self.concurrent_jobs_spin)
        
        self.retry_attempts_spin = QSpinBox()
        self.retry_attempts_spin.setRange(0, 10)
        self.retry_attempts_spin.setValue(3)
        performance_layout.addRow("Retry Attempts:", self.retry_attempts_spin)
        
        layout.addWidget(performance_group)
        
        # File handling group
        file_group = QGroupBox("File Handling")
        file_layout = QFormLayout(file_group)
        
        self.overwrite_combo = QComboBox()
        self.overwrite_combo.addItems(["skip", "replace", "unique"])
        file_layout.addRow("Overwrite Policy:", self.overwrite_combo)
        
        self.watch_folders_check = QCheckBox()
        file_layout.addRow("Watch Folders:", self.watch_folders_check)
        
        self.auto_start_check = QCheckBox()
        file_layout.addRow("Auto-start Conversions:", self.auto_start_check)
        
        layout.addWidget(file_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Processing")
    
    def _create_paths_tab(self) -> None:
        """Create paths settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Default paths group
        paths_group = QGroupBox("Default Paths")
        paths_layout = QFormLayout(paths_group)
        
        # Output directory
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(output_browse_btn)
        paths_layout.addRow("Default Output Dir:", output_layout)
        
        self.use_source_dir_check = QCheckBox()
        paths_layout.addRow("Use Source Directory:", self.use_source_dir_check)
        
        # FFmpeg path
        ffmpeg_layout = QHBoxLayout()
        self.ffmpeg_path_edit = QLineEdit()
        ffmpeg_browse_btn = QPushButton("Browse")
        ffmpeg_browse_btn.clicked.connect(self._browse_ffmpeg_path)
        ffmpeg_layout.addWidget(self.ffmpeg_path_edit)
        ffmpeg_layout.addWidget(ffmpeg_browse_btn)
        paths_layout.addRow("FFmpeg Path:", ffmpeg_layout)
        
        layout.addWidget(paths_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Paths")
    
    def _create_interface_tab(self) -> None:
        """Create interface settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "light", "dark"])
        appearance_layout.addRow("Theme:", self.theme_combo)
        
        self.high_dpi_check = QCheckBox()
        appearance_layout.addRow("High-DPI Scaling:", self.high_dpi_check)
        
        layout.addWidget(appearance_group)
        
        # Logging group
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)
        
        self.logging_combo = QComboBox()
        self.logging_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        logging_layout.addRow("Log Level:", self.logging_combo)
        
        layout.addWidget(logging_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Interface")
    
    def _load_settings(self) -> None:
        """Load current settings into dialog controls."""
        # Conversion settings
        self.format_combo.setCurrentText(self.settings.conversion.output_format)
        self.bitrate_edit.setText(self.settings.conversion.bitrate)
        self.sample_rate_spin.setValue(self.settings.conversion.sample_rate)
        self.channels_spin.setValue(self.settings.conversion.channels)
        self.normalize_loudness_check.setChecked(self.settings.conversion.normalize_loudness)
        self.normalize_peak_check.setChecked(self.settings.conversion.normalize_peak)
        self.peak_target_edit.setText(str(self.settings.conversion.peak_target))
        
        # Processing settings
        self.concurrent_jobs_spin.setValue(self.settings.processing.max_concurrent_jobs)
        self.retry_attempts_spin.setValue(self.settings.processing.retry_attempts)
        self.overwrite_combo.setCurrentText(self.settings.processing.overwrite_policy)
        self.watch_folders_check.setChecked(self.settings.processing.watch_folders)
        self.auto_start_check.setChecked(self.settings.processing.auto_start_conversions)
        
        # Path settings
        self.output_dir_edit.setText(self.settings.paths.default_output_dir)
        self.use_source_dir_check.setChecked(self.settings.paths.use_source_directory)
        self.ffmpeg_path_edit.setText(self.settings.paths.ffmpeg_path)
        
        # Interface settings
        self.theme_combo.setCurrentText(self.settings.ui.theme)
        self.high_dpi_check.setChecked(self.settings.ui.high_dpi_scaling)
        self.logging_combo.setCurrentText(self.settings.logging_level)
    
    def _save_and_accept(self) -> None:
        """Save settings and accept dialog."""
        try:
            # Conversion settings
            self.settings.conversion.output_format = self.format_combo.currentText()
            self.settings.conversion.bitrate = self.bitrate_edit.text()
            self.settings.conversion.sample_rate = self.sample_rate_spin.value()
            self.settings.conversion.channels = self.channels_spin.value()
            self.settings.conversion.normalize_loudness = self.normalize_loudness_check.isChecked()
            self.settings.conversion.normalize_peak = self.normalize_peak_check.isChecked()
            
            try:
                self.settings.conversion.peak_target = float(self.peak_target_edit.text())
            except ValueError:
                self.settings.conversion.peak_target = -1.0
            
            # Processing settings
            self.settings.processing.max_concurrent_jobs = self.concurrent_jobs_spin.value()
            self.settings.processing.retry_attempts = self.retry_attempts_spin.value()
            self.settings.processing.overwrite_policy = self.overwrite_combo.currentText()
            self.settings.processing.watch_folders = self.watch_folders_check.isChecked()
            self.settings.processing.auto_start_conversions = self.auto_start_check.isChecked()
            
            # Path settings
            self.settings.paths.default_output_dir = self.output_dir_edit.text()
            self.settings.paths.use_source_directory = self.use_source_dir_check.isChecked()
            self.settings.paths.ffmpeg_path = self.ffmpeg_path_edit.text()
            
            # Interface settings
            self.settings.ui.theme = self.theme_combo.currentText()
            self.settings.ui.high_dpi_scaling = self.high_dpi_check.isChecked()
            self.settings.logging_level = self.logging_combo.currentText()
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
    
    def _browse_output_dir(self) -> None:
        """Browse for default output directory."""
        current_dir = self.output_dir_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Default Output Directory", current_dir
        )
        if folder:
            self.output_dir_edit.setText(folder)
    
    def _browse_ffmpeg_path(self) -> None:
        """Browse for FFmpeg executable."""
        current_path = self.ffmpeg_path_edit.text() or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FFmpeg Executable", current_path,
            "Executable Files (*.exe);;All Files (*)" if Path.cwd().drive else "All Files (*)"
        )
        if file_path:
            self.ffmpeg_path_edit.setText(file_path)
    
    def get_settings(self) -> Settings:
        """Get the modified settings."""
        return self.settings


class AboutDialog(QDialog):
    """About dialog showing application information."""
    
    def __init__(self, parent=None) -> None:
        """Initialize about dialog."""
        super().__init__(parent)
        
        self.setWindowTitle("About Vid2Aud")
        self.setModal(True)
        self.setFixedSize(400, 300)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Application info
        title_label = QLabel("Vid2Aud")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        description_label = QLabel(
            "A professional cross-platform desktop GUI application "
            "for converting video files to audio formats at scale."
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description_label)
        
        layout.addStretch()
        
        # Copyright and license
        copyright_label = QLabel("© 2024 Video Converter Team")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)
        
        license_label = QLabel("Licensed under MIT License")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)
        
        # Credits
        credits_text = QTextEdit()
        credits_text.setMaximumHeight(80)
        credits_text.setReadOnly(True)
        credits_text.setPlainText(
            "Built with:\n"
            "• Python 3.10+\n"
            "• PySide6 (Qt6)\n"
            "• FFmpeg\n"
            "• appdirs"
        )
        layout.addWidget(credits_text)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class FFmpegHelpDialog(QDialog):
    """Dialog showing FFmpeg installation help."""
    
    def __init__(self, parent=None) -> None:
        """Initialize FFmpeg help dialog."""
        super().__init__(parent)
        
        self.setWindowTitle("FFmpeg Installation Help")
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("FFmpeg Not Found")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "Vid2Aud requires FFmpeg to convert video files to audio. "
            "Please install FFmpeg using one of the methods below:"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Installation instructions
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText(self._get_installation_instructions())
        layout.addWidget(help_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        test_button = QPushButton("Test FFmpeg")
        test_button.clicked.connect(self._test_ffmpeg)
        button_layout.addWidget(test_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _get_installation_instructions(self) -> str:
        """Get platform-specific installation instructions."""
        instructions = """
WINDOWS:

Option 1: Using Chocolatey (Recommended)
1. Install Chocolatey from https://chocolatey.org/
2. Open Command Prompt as Administrator
3. Run: choco install ffmpeg

Option 2: Using Scoop
1. Install Scoop from https://scoop.sh/
2. Open PowerShell
3. Run: scoop install ffmpeg

Option 3: Manual Installation
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., C:\\ffmpeg)
3. Add the bin folder to your System PATH
4. Restart your computer

MACOS:

Using Homebrew (Recommended)
1. Install Homebrew from https://brew.sh/
2. Open Terminal
3. Run: brew install ffmpeg

Using MacPorts
1. Install MacPorts from https://www.macports.org/
2. Run: sudo port install ffmpeg

LINUX:

Ubuntu/Debian:
sudo apt update && sudo apt install ffmpeg

Fedora:
sudo dnf install ffmpeg

Arch Linux:
sudo pacman -S ffmpeg

CentOS/RHEL:
sudo yum install epel-release
sudo yum install ffmpeg

VERIFICATION:

After installation, verify FFmpeg is working by opening a terminal/command prompt and running:
ffmpeg -version

You should see version information displayed.

If FFmpeg is installed but not found, you can specify a custom path in Settings → Paths → FFmpeg Path.
        """
        return instructions.strip()
    
    def _test_ffmpeg(self) -> None:
        """Test if FFmpeg is available."""
        try:
            from ..converter import AudioConverter
            
            converter = AudioConverter()
            QMessageBox.information(
                self, "FFmpeg Test", "FFmpeg is working correctly!"
            )
        except Exception as e:
            QMessageBox.warning(
                self, "FFmpeg Test Failed", 
                f"FFmpeg test failed:\n{str(e)}\n\n"
                "Please follow the installation instructions above."
            )