"""Application bootstrap with theme support and exception handling."""

import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QLocale, QTranslator, Qt
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from ..settings import get_settings, get_settings_manager
from .main_window import MainWindow

logger = logging.getLogger(__name__)


class Vid2AudApplication(QApplication):
    """Custom QApplication with theme and internationalization support."""
    
    def __init__(self, argv: list[str]) -> None:
        """Initialize application with custom settings."""
        super().__init__(argv)
        
        # Set application properties
        self.setApplicationName("Vid2Aud")
        self.setApplicationDisplayName("Video to Audio Converter")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("Vid2AudTeam")
        self.setOrganizationDomain("vid2aud.com")
        
        # Initialize settings
        self.settings_manager = get_settings_manager()
        self.settings = get_settings()
        
        # Setup logging
        self.settings_manager.setup_logging(self.settings.logging_level)
        
        # Setup high DPI (for Qt versions that support it)
        if self.settings.ui.high_dpi_scaling:
            try:
                # These are deprecated in newer Qt versions but still work
                self.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
                self.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
            except AttributeError:
                # For newer Qt versions, high DPI is enabled by default
                pass
        
        # Install exception handler
        sys.excepthook = self._handle_exception
        
        # Load translations
        self._load_translations()
        
        # Apply theme
        self._apply_theme()
        
        # Load application icon
        self._load_app_icon()
        
        logger.info("Application initialized")
    
    def _handle_exception(
        self, 
        exc_type: type, 
        exc_value: Exception, 
        traceback_obj
    ) -> None:
        """Handle uncaught exceptions."""
        import traceback
        
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, traceback_obj))
        logger.critical(f"Uncaught exception: {error_msg}")
        
        # Show error dialog
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Application Error")
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText("An unexpected error occurred.")
        msg_box.setDetailedText(error_msg)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def _load_translations(self) -> None:
        """Load application translations."""
        translator = QTranslator()
        
        # Determine locale
        locale = QLocale.system()
        locale_name = locale.name()
        
        # Look for translation files
        app_dir = Path(__file__).parent.parent.parent.parent
        locale_dir = app_dir / "locale"
        
        translation_file = locale_dir / locale_name / "vid2aud.qm"
        
        if translation_file.exists():
            if translator.load(str(translation_file)):
                self.installTranslator(translator)
                logger.info(f"Loaded translations for {locale_name}")
            else:
                logger.warning(f"Failed to load translations for {locale_name}")
        else:
            logger.debug(f"No translations found for {locale_name}")
    
    def _apply_theme(self) -> None:
        """Apply application theme."""
        theme = self.settings.ui.theme
        
        if theme == "system":
            # Use system theme (default)
            pass
        elif theme == "dark":
            self._apply_dark_theme()
        elif theme == "light":
            self._apply_light_theme()
        
        logger.debug(f"Applied {theme} theme")
    
    def _apply_dark_theme(self) -> None:
        """Apply dark theme."""
        dark_palette = QPalette()
        
        # Window colors
        dark_palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        
        # Base colors (for input fields)
        dark_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.black)
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, Qt.GlobalColor.darkGray)
        
        # Text colors
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        
        # Button colors
        dark_palette.setColor(QPalette.ColorRole.Button, Qt.GlobalColor.darkGray)
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        
        # Highlight colors
        dark_palette.setColor(QPalette.ColorRole.Highlight, Qt.GlobalColor.blue)
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        # Link colors
        dark_palette.setColor(QPalette.ColorRole.Link, Qt.GlobalColor.cyan)
        dark_palette.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.magenta)
        
        self.setPalette(dark_palette)
    
    def _apply_light_theme(self) -> None:
        """Apply light theme."""
        # Reset to default light palette
        self.setPalette(QApplication.style().standardPalette())
    
    def _load_app_icon(self) -> None:
        """Load application icon."""
        import sys
        import os
        
        # Determine if we're running as a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS)
            icon_paths = [
                str(bundle_dir / "assets" / "icons" / "app.svg"),
                str(bundle_dir / "assets" / "icons" / "app.png"),
                str(bundle_dir / "assets" / "icons" / "app.ico"),
                str(bundle_dir / "assets" / "icons" / "app.icns"),
            ]
        else:
            # Running from source
            project_root = Path(__file__).parent.parent.parent.parent
            icon_paths = [
                ":/icons/app.svg",
                ":/icons/app.png", 
                str(project_root / "assets" / "icons" / "app.svg"),
                str(project_root / "assets" / "icons" / "app.png"),
                str(project_root / "assets" / "icons" / "app.ico"),
                str(project_root / "assets" / "icons" / "app.icns"),
            ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    logger.debug(f"Loaded application icon from {icon_path}")
                    break
        else:
            logger.debug("No application icon found, using default")


def create_main_window(app: Vid2AudApplication) -> MainWindow:
    """Create and setup main window."""
    main_window = MainWindow()
    
    # Restore window state
    ui_settings = app.settings.ui
    main_window.resize(ui_settings.window_width, ui_settings.window_height)
    
    if ui_settings.window_maximized:
        main_window.showMaximized()
    else:
        main_window.show()
    
    # Check for session recovery
    session_state = app.settings_manager.load_session_state()
    if session_state:
        reply = QMessageBox.question(
            main_window,
            "Restore Session",
            "A previous session was found. Would you like to restore it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            main_window.restore_session(session_state)
        else:
            app.settings_manager.clear_session_state()
    
    return main_window


def main() -> int:
    """Main application entry point."""
    try:
        # Create application
        app = Vid2AudApplication(sys.argv)
        
        # Create main window
        main_window = create_main_window(app)
        
        # Setup cleanup on exit
        def cleanup() -> None:
            """Cleanup before application exit."""
            try:
                # Save settings
                app.settings_manager.save_settings(app.settings)
                
                # Save session state
                main_window.save_session_state()
                
                # Stop worker
                if hasattr(main_window, 'worker'):
                    main_window.worker.stop_processing(timeout=5.0)
                
                logger.info("Application cleanup completed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        app.aboutToQuit.connect(cleanup)
        
        # Run application
        return app.exec()
        
    except Exception as e:
        # Fallback error handling if Qt is not available
        print(f"Failed to start application: {e}")
        logging.critical(f"Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())