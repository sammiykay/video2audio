"""Main application window with drag-drop support and job management."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..converter import AudioConverter, ConversionParams, FFmpegNotFoundError
from ..fsutils import FileFilter, PathUtils, ValidationError, get_safe_output_directory
from ..settings import get_settings, get_settings_manager, save_settings
from ..worker import ConversionJob, ConversionWorker, JobStatus
from .dialogs import AboutDialog, FFmpegHelpDialog, SettingsDialog

logger = logging.getLogger(__name__)


class JobTableModel(QAbstractTableModel):
    """Table model for conversion jobs."""
    
    COLUMNS = [
        ("Source", "source"),
        ("Target", "target"), 
        ("Status", "status"),
        ("Progress", "progress"),
        ("Duration", "duration"),
        ("ETA", "eta"),
        ("Message", "message")
    ]
    
    def __init__(self, parent=None) -> None:
        """Initialize job table model."""
        super().__init__(parent)
        self.jobs: List[ConversionJob] = []
    
    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of rows."""
        return len(self.jobs)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        """Return number of columns."""
        return len(self.COLUMNS)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return header data."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][0]
        return None
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return cell data."""
        if not index.isValid() or not (0 <= index.row() < len(self.jobs)):
            return None
        
        job = self.jobs[index.row()]
        column_key = self.COLUMNS[index.column()][1]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(job, column_key)
        elif role == Qt.ItemDataRole.UserRole:
            return job  # Return the job object for context menus
        
        return None
    
    def _get_display_value(self, job: ConversionJob, column_key: str) -> str:
        """Get display value for a job column."""
        if column_key == "source":
            return job.input_path.name
        elif column_key == "target":
            return job.output_path.name
        elif column_key == "status":
            return job.status.name.title()
        elif column_key == "progress":
            if job.status == JobStatus.RUNNING:
                return f"{job.progress * 100:.1f}%"
            elif job.status in (JobStatus.COMPLETED, JobStatus.SKIPPED):
                return "100%"
            return ""
        elif column_key == "duration":
            if job.started_at:
                duration = job.duration
                if duration > 0:
                    return f"{duration:.1f}s"
            return ""
        elif column_key == "eta":
            if job.status == JobStatus.RUNNING:
                eta = job.eta_seconds
                if eta is not None:
                    return f"{eta:.0f}s"
            return ""
        elif column_key == "message":
            if job.status == JobStatus.FAILED:
                return job.error_message
            elif job.status == JobStatus.SKIPPED:
                return "File already exists"
            elif job.status == JobStatus.COMPLETED:
                return "Success"
            return ""
        
        return ""
    
    def update_jobs(self, jobs: List[ConversionJob]) -> None:
        """Update the job list and refresh the view."""
        self.beginResetModel()
        self.jobs = jobs.copy()
        self.endResetModel()
    
    def get_job(self, row: int) -> Optional[ConversionJob]:
        """Get job at specific row."""
        if 0 <= row < len(self.jobs):
            return self.jobs[row]
        return None


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self) -> None:
        """Initialize main window."""
        super().__init__()
        
        self.settings_manager = get_settings_manager()
        self.settings = get_settings()
        
        # Initialize worker
        self.worker = ConversionWorker(self.settings.processing.max_concurrent_jobs)
        
        # UI Components
        self.job_model = JobTableModel()
        self.update_timer = QTimer()
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._setup_drag_drop()
        
        # Start update timer
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(1000)  # Update every second
        
        logger.info("Main window initialized")
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        self.setWindowTitle("Video to Audio Converter")
        self.setMinimumSize(800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        self._create_toolbar()
        
        # Create controls section
        controls_widget = self._create_controls_section()
        main_layout.addWidget(controls_widget)
        
        # Create splitter for table and log
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Create job table
        table_widget = self._create_job_table()
        splitter.addWidget(table_widget)
        
        # Create log panel
        log_widget = self._create_log_panel()
        splitter.addWidget(log_widget)
        
        # Set splitter sizes
        splitter.setSizes(self.settings.ui.splitter_sizes)
        main_layout.addWidget(splitter)
        
        # Create status bar
        self._create_status_bar()
    
    def _create_toolbar(self) -> None:
        """Create main toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        
        # Add Files
        add_files_action = QAction("Add Files", self)
        add_files_action.setShortcut(QKeySequence.StandardKey.Open)
        add_files_action.triggered.connect(self._add_files)
        toolbar.addAction(add_files_action)
        
        # Add Folder
        add_folder_action = QAction("Add Folder", self)
        add_folder_action.triggered.connect(self._add_folder)
        toolbar.addAction(add_folder_action)
        
        toolbar.addSeparator()
        
        
        toolbar.addSeparator()
        
        # Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(settings_action)
        
        # Help
        help_action = QAction("Help", self)
        help_action.triggered.connect(self._show_help)
        toolbar.addAction(help_action)
    
    def _create_controls_section(self) -> QWidget:
        """Create conversion controls section."""
        controls_widget = QWidget()
        main_layout = QVBoxLayout(controls_widget)
        
        # Settings group
        settings_group = QGroupBox("Conversion Settings")
        settings_layout = QHBoxLayout(settings_group)
        
        # Output directory
        settings_layout.addWidget(QLabel("Output Dir:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Use source directory")
        settings_layout.addWidget(self.output_dir_edit)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output_dir)
        settings_layout.addWidget(browse_btn)
        
        # Format selection
        settings_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "wav", "m4a", "flac"])
        self.format_combo.setCurrentText(self.settings.conversion.output_format)
        settings_layout.addWidget(self.format_combo)
        
        # Quality selection
        settings_layout.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.setEditable(True)
        self.bitrate_combo.addItems(["128k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText(self.settings.conversion.bitrate)
        settings_layout.addWidget(self.bitrate_combo)
        
        main_layout.addWidget(settings_group)
        
        # Control buttons group
        control_group = QGroupBox("Process Control")
        control_layout = QHBoxLayout(control_group)
        
        # Start/Stop button (prominent)
        self.start_stop_btn = QPushButton("▶ START CONVERSION")
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 200px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_stop_btn.clicked.connect(self._toggle_conversion)
        control_layout.addWidget(self.start_stop_btn)
        
        control_layout.addSpacing(20)
        
        # Pause button
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        control_layout.addWidget(self.pause_btn)
        
        # Clear button
        clear_btn = QPushButton("🗑 Clear Completed")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        clear_btn.clicked.connect(self._clear_completed)
        control_layout.addWidget(clear_btn)
        
        control_layout.addStretch()
        
        main_layout.addWidget(control_group)
        
        return controls_widget
    
    def _create_job_table(self) -> QWidget:
        """Create job table widget."""
        table_group = QGroupBox("Conversion Queue")
        layout = QVBoxLayout(table_group)
        
        self.job_table = QTableView()
        self.job_table.setModel(self.job_model)
        self.job_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.job_table.setAlternatingRowColors(True)
        
        # Configure column widths
        header = self.job_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # Set initial column widths
        for i, (_, key) in enumerate(self.job_model.COLUMNS):
            if key in self.settings.ui.table_column_widths:
                width = self.settings.ui.table_column_widths[key]
                self.job_table.setColumnWidth(i, width)
        
        layout.addWidget(self.job_table)
        
        # Progress bar
        self.global_progress = QProgressBar()
        self.global_progress.setVisible(False)
        layout.addWidget(self.global_progress)
        
        return table_group
    
    def _create_log_panel(self) -> QWidget:
        """Create log panel widget."""
        log_group = QGroupBox("Activity Log")
        layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        return log_group
    
    def _create_status_bar(self) -> None:
        """Create status bar."""
        status_bar = self.statusBar()
        
        # Job counts
        self.status_label = QLabel("Ready")
        status_bar.addWidget(self.status_label)
        
        # Permanent widgets
        self.stats_label = QLabel("0 jobs")
        status_bar.addPermanentWidget(self.stats_label)
    
    def _setup_drag_drop(self) -> None:
        """Setup drag and drop functionality."""
        self.setAcceptDrops(True)
    
    def _connect_signals(self) -> None:
        """Connect worker signals to UI slots."""
        # Worker signals
        self.worker.signals.job_started.connect(self._on_job_started)
        self.worker.signals.job_progress.connect(self._on_job_progress)
        self.worker.signals.job_completed.connect(self._on_job_completed)
        self.worker.signals.job_failed.connect(self._on_job_failed)
        self.worker.signals.job_cancelled.connect(self._on_job_cancelled)
        self.worker.signals.job_skipped.connect(self._on_job_skipped)
        self.worker.signals.queue_updated.connect(self._on_queue_updated)
        self.worker.signals.all_jobs_completed.connect(self._on_all_jobs_completed)
        self.worker.signals.worker_error.connect(self._on_worker_error)
    
    def _add_files(self) -> None:
        """Add files to conversion queue."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter(
            "Video Files (*.mp4 *.mkv *.mov *.avi *.wmv *.flv *.webm *.m4v *.3gp);;All Files (*)"
        )
        
        if file_dialog.exec():
            files = [Path(f) for f in file_dialog.selectedFiles()]
            self._add_files_to_queue(files)
    
    def _add_folder(self) -> None:
        """Add folder contents to conversion queue."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._scan_folder(Path(folder))
    
    def _scan_folder(self, folder_path: Path) -> None:
        """Scan folder for video files."""
        try:
            # Create file filter
            supported_extensions = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}
            file_filter = FileFilter(
                include_patterns=["*"],
                supported_extensions=supported_extensions
            )
            
            # Scan directory
            files = file_filter.scan_directory(folder_path, recursive=True)
            
            if files:
                self._add_files_to_queue(files)
                self._log_message(f"Found {len(files)} files in {folder_path}")
            else:
                self._log_message(f"No supported video files found in {folder_path}")
                
        except ValidationError as e:
            QMessageBox.warning(self, "Folder Scan Error", str(e))
    
    def _add_files_to_queue(self, files: List[Path]) -> None:
        """Add multiple files to the conversion queue."""
        if not files:
            return
        
        try:
            # Get output directory
            output_dir = self._get_output_directory(files[0] if files else None)
            # Note: output_dir can be None if using source directories
            
            # Create conversion parameters
            params = self._create_conversion_params()
            
            # Add files to worker
            results = self.worker.add_batch_jobs(
                files, 
                output_dir, 
                params, 
                self.settings.processing.overwrite_policy
            )
            
            # Count results
            added_count = sum(1 for success in results.values() if success)
            
            # Log with appropriate message
            if output_dir:
                self._log_message(f"Added {added_count}/{len(files)} files to queue → {output_dir}")
            else:
                self._log_message(f"Added {added_count}/{len(files)} files to queue → source directories")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add files: {str(e)}")
    
    def _get_output_directory(self, sample_file: Optional[Path] = None) -> Optional[Path]:
        """Get output directory from UI or settings."""
        output_dir_text = self.output_dir_edit.text().strip()
        
        if output_dir_text:
            # User specified an output directory
            output_dir = Path(output_dir_text)
            if not output_dir.exists():
                reply = QMessageBox.question(
                    self,
                    "Create Directory",
                    f"Output directory does not exist:\n{output_dir}\n\nCreate it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        output_dir.mkdir(parents=True, exist_ok=True)
                    except OSError as e:
                        QMessageBox.critical(self, "Error", f"Failed to create directory: {e}")
                        return None
                else:
                    return None
            return output_dir
        else:
            # Return None to use source directories (handled by worker)
            return None
    
    def _create_conversion_params(self) -> ConversionParams:
        """Create conversion parameters from UI settings."""
        return ConversionParams(
            output_format=self.format_combo.currentText(),
            codec=AudioConverter.get_default_codec(self.format_combo.currentText()),
            bitrate=self.bitrate_combo.currentText(),
            sample_rate=self.settings.conversion.sample_rate,
            channels=self.settings.conversion.channels,
            normalize_loudness=self.settings.conversion.normalize_loudness,
            normalize_peak=self.settings.conversion.normalize_peak,
            peak_target=self.settings.conversion.peak_target,
        )
    
    def _browse_output_dir(self) -> None:
        """Browse for output directory."""
        current_dir = self.output_dir_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", current_dir
        )
        if folder:
            self.output_dir_edit.setText(folder)
    
    def _toggle_conversion(self) -> None:
        """Toggle start/stop conversion process."""
        if self.start_stop_btn.text().startswith("▶"):
            # Start conversion
            try:
                if not self.worker._converter:
                    self.worker.initialize_converter(self.settings.paths.ffmpeg_path or None)
            except FFmpegNotFoundError:
                self._show_ffmpeg_help()
                return
            
            # Check if there are jobs to process
            stats = self.worker.get_queue_stats()
            if stats['total'] == 0:
                QMessageBox.information(
                    self, "No Jobs", 
                    "Please add some video files to convert first.\n\n"
                    "You can:\n"
                    "• Drag and drop files into the window\n"
                    "• Use 'Add Files' or 'Add Folder' buttons"
                )
                return
            
            self.worker.start_processing()
            
            # Update UI state
            self.start_stop_btn.setText("⏹ STOP CONVERSION")
            self.start_stop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 200px;
                    min-height: 40px;
                }
                QPushButton:hover {
                    background-color: #D32F2F;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            self.pause_btn.setEnabled(True)
            
            self._log_message("Started conversion process")
        else:
            # Stop conversion
            reply = QMessageBox.question(
                self,
                "Stop Conversion",
                "Are you sure you want to stop all conversions?\n\n"
                "Currently running jobs will be cancelled.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop_processing()
                
                # Update UI state
                self.start_stop_btn.setText("▶ START CONVERSION")
                self.start_stop_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 12px 24px;
                        font-size: 14px;
                        font-weight: bold;
                        min-width: 200px;
                        min-height: 40px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:disabled {
                        background-color: #cccccc;
                        color: #666666;
                    }
                """)
                self.pause_btn.setEnabled(False)
                self.pause_btn.setText("⏸ Pause")
                
                self._log_message("Stopped conversion process")
    
    def _toggle_pause(self) -> None:
        """Toggle pause/resume conversion."""
        if self.pause_btn.text() == "⏸ Pause":
            self.worker.pause_processing()
            self.pause_btn.setText("▶ Resume")
            self._log_message("Paused conversion process")
        else:
            self.worker.resume_processing()
            self.pause_btn.setText("⏸ Pause")
            self._log_message("Resumed conversion process")
    
    
    def _clear_completed(self) -> None:
        """Clear completed jobs from the queue."""
        self.worker.clear_completed_jobs()
        self._log_message("Cleared completed jobs")
    
    def _show_settings(self) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            save_settings(self.settings)
            self._apply_settings()
    
    def _show_help(self) -> None:
        """Show help/about dialog."""
        AboutDialog(self).exec()
    
    def _show_ffmpeg_help(self) -> None:
        """Show FFmpeg installation help."""
        FFmpegHelpDialog(self).exec()
    
    def _apply_settings(self) -> None:
        """Apply settings to UI and worker."""
        # Update worker settings
        self.worker.max_workers = self.settings.processing.max_concurrent_jobs
        
        # Update UI controls
        self.format_combo.setCurrentText(self.settings.conversion.output_format)
        self.bitrate_combo.setCurrentText(self.settings.conversion.bitrate)
    
    def _update_display(self) -> None:
        """Update display with current job status."""
        jobs = self.worker.get_all_jobs()
        self.job_model.update_jobs(jobs)
        
        # Update stats
        stats = self.worker.get_queue_stats()
        self.stats_label.setText(
            f"{stats['total']} jobs ({stats['running']} running, "
            f"{stats['completed']} done, {stats['failed']} failed)"
        )
        
        # Update global progress
        if stats['running'] > 0:
            if not self.global_progress.isVisible():
                self.global_progress.setVisible(True)
            
            # Calculate overall progress
            total_progress = 0.0
            active_jobs = 0
            for job in jobs:
                if job.status == JobStatus.RUNNING:
                    total_progress += job.progress
                    active_jobs += 1
                elif job.status in (JobStatus.COMPLETED, JobStatus.SKIPPED):
                    total_progress += 1.0
                    active_jobs += 1
            
            if active_jobs > 0:
                progress = (total_progress / active_jobs) * 100
                self.global_progress.setValue(int(progress))
        else:
            self.global_progress.setVisible(False)
    
    def _log_message(self, message: str) -> None:
        """Add message to activity log."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Keep log size reasonable
        if self.log_text.document().blockCount() > 1000:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()
    
    # Worker signal handlers
    def _on_job_started(self, job_id: str) -> None:
        """Handle job started signal."""
        self._log_message(f"Started: {job_id}")
    
    def _on_job_progress(self, job_id: str, progress: float) -> None:
        """Handle job progress signal."""
        pass  # Progress is shown via model update
    
    def _on_job_completed(self, job_id: str, result) -> None:
        """Handle job completed signal."""
        self._log_message(f"Completed: {job_id}")
    
    def _on_job_failed(self, job_id: str, error_message: str) -> None:
        """Handle job failed signal."""
        self._log_message(f"Failed: {job_id} - {error_message}")
    
    def _on_job_cancelled(self, job_id: str) -> None:
        """Handle job cancelled signal."""
        self._log_message(f"Cancelled: {job_id}")
    
    def _on_job_skipped(self, job_id: str, reason: str) -> None:
        """Handle job skipped signal."""
        self._log_message(f"Skipped: {job_id} - {reason}")
    
    def _on_queue_updated(self) -> None:
        """Handle queue updated signal."""
        pass  # Handled by timer update
    
    def _on_all_jobs_completed(self, stats: Dict[str, Any]) -> None:
        """Handle all jobs completed signal."""
        self._log_message(
            f"All jobs completed: {stats['completed']} successful, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        
        # Reset UI state
        self.start_stop_btn.setText("▶ START CONVERSION")
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 200px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Pause")
    
    def _on_worker_error(self, error_message: str) -> None:
        """Handle worker error signal."""
        self._log_message(f"Worker error: {error_message}")
        QMessageBox.critical(self, "Worker Error", error_message)
    
    # Drag and drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event."""
        urls = event.mimeData().urls()
        files = []
        
        for url in urls:
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file():
                    if AudioConverter.is_supported_format(path):
                        files.append(path)
                elif path.is_dir():
                    # Scan directory
                    self._scan_folder(path)
        
        if files:
            self._add_files_to_queue(files)
        
        event.acceptProposedAction()
    
    # Session management
    def save_session_state(self) -> None:
        """Save current session state."""
        try:
            # Get current jobs
            jobs = self.worker.get_all_jobs()
            queue_items = []
            
            for job in jobs:
                if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    queue_items.append({
                        "input_path": str(job.input_path),
                        "output_path": str(job.output_path),
                        "params": {
                            "output_format": job.params.output_format,
                            "codec": job.params.codec,
                            "bitrate": job.params.bitrate,
                            "sample_rate": job.params.sample_rate,
                            "channels": job.params.channels,
                        }
                    })
            
            # Get window state
            window_state = {
                "geometry": [self.x(), self.y(), self.width(), self.height()],
                "maximized": self.isMaximized(),
            }
            
            self.settings_manager.save_session_state(queue_items, window_state)
            
        except Exception as e:
            logger.warning(f"Failed to save session state: {e}")
    
    def restore_session(self, session_state: Dict[str, Any]) -> None:
        """Restore session from saved state."""
        try:
            queue_items = session_state.get("queue_items", [])
            
            for item in queue_items:
                input_path = Path(item["input_path"])
                output_path = Path(item["output_path"])
                
                # Recreate conversion params
                params_data = item["params"]
                params = ConversionParams(**params_data)
                
                # Add to queue
                job_id = f"restored_{input_path.stem}_{len(self.worker.get_all_jobs())}"
                self.worker.add_job(job_id, input_path, output_path, params)
            
            if queue_items:
                self._log_message(f"Restored {len(queue_items)} jobs from previous session")
            
        except Exception as e:
            logger.warning(f"Failed to restore session: {e}")
    
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Stop worker
        self.worker.stop_processing(timeout=5.0)
        
        # Save settings
        self.settings.ui.window_width = self.width()
        self.settings.ui.window_height = self.height()
        self.settings.ui.window_maximized = self.isMaximized()
        save_settings(self.settings)
        
        event.accept()