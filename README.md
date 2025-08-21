# Vid2Aud - Video to Audio Converter

A professional cross-platform desktop GUI application for converting video files to audio formats at scale. Built with Python and PySide6, featuring batch processing, real-time progress tracking, and robust error handling.

![Vid2Aud Screenshot](assets/screenshots/main-window.png)

## ✨ Features

### Core Functionality
- **Batch Processing**: Convert multiple files simultaneously with configurable concurrency
- **Format Support**: Convert to MP3, WAV, M4A, FLAC with customizable codecs and bitrates
- **Progress Tracking**: Real-time progress bars, ETA estimates, and completion status
- **Drag & Drop**: Simply drag video files or folders into the application
- **Metadata Preservation**: Copy title, artist, album, and other metadata to output files
- **Audio Normalization**: EBU R128 loudness normalization or peak normalization options

### User Interface
- **Modern GUI**: Clean, responsive interface built with PySide6/Qt
- **Theme Support**: Light, dark, or system theme with high-DPI scaling
- **Session Recovery**: Restore interrupted conversion queues after crashes
- **Activity Logging**: Detailed conversion logs with timestamps and error details
- **Keyboard Shortcuts**: Full keyboard navigation and shortcuts
- **Internationalization**: Ready for multiple language support

### Advanced Features
- **Smart Overwrite Policies**: Skip, replace, or create unique filenames
- **Time Trimming**: Extract specific time ranges from videos
- **Stream Selection**: Choose specific audio streams from multi-track files
- **Watch Folders**: Automatically process new files dropped into folders
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Cross-Platform Settings**: Persistent settings across Windows, macOS, and Linux

## 🎯 Supported Formats

### Input Video Formats
- MP4, MKV, MOV, AVI, WMV, FLV, WebM, M4V, 3GP
- Any format supported by your FFmpeg installation

### Output Audio Formats
- **MP3**: LAME encoder, 128k-320k bitrate
- **WAV**: PCM 16-bit, uncompressed
- **M4A**: AAC encoder, Apple format
- **FLAC**: Lossless compression
- **OGG**: Vorbis encoder

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- FFmpeg installed and available in PATH
- Windows 10+, macOS 10.14+, or Linux with GUI support

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vid2aud/vid2aud-gui.git
   cd vid2aud-gui
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   ```

3. **Install FFmpeg** (if not already installed):
   
   **Windows (Chocolatey):**
   ```cmd
   choco install ffmpeg
   ```
   
   **Windows (Scoop):**
   ```cmd
   scoop install ffmpeg
   ```
   
   **macOS (Homebrew):**
   ```bash
   brew install ffmpeg
   ```
   
   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt update && sudo apt install ffmpeg
   ```
   
   **Linux (Fedora):**
   ```bash
   sudo dnf install ffmpeg
   ```

4. **Run the application:**
   ```bash
   vid2aud
   # or
   python -m vid2aud.gui.app
   ```

### First Use

1. Launch Vid2Aud
2. Drag video files or folders into the main window
3. Select output format and quality settings
4. Choose output directory (or use source directories)
5. Click "Start" to begin conversion
6. Monitor progress in real-time

## 📖 Usage Guide

### Adding Files

**Method 1: Drag & Drop**
- Drag video files directly into the application window
- Drag folders to recursively scan for video files
- Mixed file and folder drops are supported

**Method 2: File Browser**
- Click "Add Files" to select individual files
- Click "Add Folder" to scan a directory
- Use Ctrl+O keyboard shortcut for quick file addition

### Conversion Settings

**Output Format**
- Choose from MP3, WAV, M4A, FLAC formats
- Codec automatically selected based on format
- Custom codec selection available in Settings

**Quality Settings**
- **Bitrate**: 128k, 192k, 256k, 320k (or custom)
- **Sample Rate**: 44100 Hz, 48000 Hz, 96000 Hz
- **Channels**: Mono (1) or Stereo (2)

**Advanced Options** (via Settings)
- Audio normalization (loudness or peak)
- Time trimming (start/end times)
- Audio stream selection for multi-track files
- Metadata preservation options

### Managing Conversion Queue

**Job Control**
- **Start**: Begin processing queued jobs
- **Pause/Resume**: Temporarily halt and resume processing
- **Cancel All**: Stop all jobs (running jobs complete current file)
- **Clear Completed**: Remove finished jobs from the list

**Individual Job Actions** (right-click menu)
- Open source file location
- Open output file (if completed)
- Copy error message (if failed)
- Remove from queue

### Monitoring Progress

**Job Table Columns**
- **Source**: Input filename
- **Target**: Output filename
- **Status**: Current job state (Queued/Running/Completed/Failed/Skipped)
- **Progress**: Completion percentage for active jobs
- **Duration**: Time elapsed since job started
- **ETA**: Estimated time remaining
- **Message**: Success confirmation or error details

**Status Indicators**
- 🟢 **Completed**: Job finished successfully
- 🔄 **Running**: Currently converting
- ⏳ **Queued**: Waiting to start
- ❌ **Failed**: Error occurred during conversion
- ⏭️ **Skipped**: File already exists (skip policy)
- 🚫 **Cancelled**: User cancelled job

## ⚙️ Configuration

### Settings Dialog

Access via toolbar Settings button or Ctrl+, shortcut:

**Conversion Tab**
- Default output format and codec
- Quality settings (bitrate, sample rate, channels)
- Audio normalization options
- Time trimming defaults

**Processing Tab**
- Maximum concurrent jobs (1-16)
- Retry attempts and backoff settings
- Overwrite policy (skip/replace/unique)
- Watch folder automation

**Paths Tab**
- Default output directory
- Custom FFmpeg path
- Recent directory shortcuts

**Interface Tab**
- Theme selection (system/light/dark)
- High-DPI scaling toggle
- Column width preferences
- Logging level

### Advanced Configuration

**Settings File Location**
- **Windows**: `%APPDATA%\Vid2AudTeam\Vid2Aud\settings.json`
- **macOS**: `~/Library/Application Support/Vid2Aud/settings.json`
- **Linux**: `~/.config/Vid2Aud/settings.json`

**Log Files**
- **Windows**: `%APPDATA%\Vid2AudTeam\Vid2Aud\Logs\vid2aud.log`
- **macOS**: `~/Library/Logs/Vid2Aud/vid2aud.log`
- **Linux**: `~/.local/share/Vid2Aud/vid2aud.log`

## 🔧 Building and Distribution

### Development Setup

```bash
# Clone repository
git clone https://github.com/vid2aud/vid2aud-gui.git
cd vid2aud-gui

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Code formatting
ruff check src/
ruff format src/
```

### Building Executables

**Windows Executable**
```bash
pip install pyinstaller
pyinstaller build/pyinstaller_win.spec
```

**macOS App Bundle**
```bash
pip install pyinstaller
pyinstaller build/pyinstaller_mac.spec
# For distribution:
# codesign --deep --force --verify --verbose --sign "Developer ID" dist/Vid2Aud.app
# hdiutil create -volname "Vid2Aud" -srcfolder dist/Vid2Aud.app -ov -format UDZO dist/Vid2Aud.dmg
```

**Linux AppImage**
```bash
# Install appimagetool
pip install pyinstaller
pyinstaller build/pyinstaller_linux.spec
# Use appimagetool to create AppImage from dist/
```

### Distribution Notes

**Code Signing**
- Windows: Use SignTool with a valid code signing certificate
- macOS: Use Developer ID certificate and notarization
- Linux: GPG signing recommended for package managers

**Dependencies**
- All Python dependencies are bundled in executable builds
- FFmpeg must be installed separately by end users
- Qt libraries are included automatically by PyInstaller

## 🐛 Troubleshooting

### Common Issues

**FFmpeg Not Found**
- **Error**: "FFmpeg not found in PATH"
- **Solution**: Install FFmpeg and ensure it's in system PATH
- **Alternative**: Specify custom FFmpeg path in Settings → Paths

**Permission Denied**
- **Error**: "Permission denied" when writing output files
- **Solution**: Run as administrator or check output directory permissions
- **Tip**: Avoid system directories like Program Files or Windows

**Codec Not Supported**
- **Error**: "Codec not supported" or encoding failures
- **Solution**: Update FFmpeg to latest version
- **Alternative**: Try different output format or codec

**Unicode Path Issues**
- **Error**: Conversion fails with non-English filenames
- **Solution**: Ensure FFmpeg supports Unicode (latest versions do)
- **Workaround**: Rename files to ASCII characters temporarily

**High Memory Usage**
- **Cause**: Processing many large files simultaneously
- **Solution**: Reduce concurrent jobs in Settings → Processing
- **Recommendation**: 2-4 concurrent jobs for most systems

**Antivirus False Positives**
- **Issue**: Antivirus software blocks executable
- **Solution**: Add Vid2Aud to antivirus exclusions
- **Note**: Common with PyInstaller-built executables

### Performance Optimization

**For Large Files**
- Reduce concurrent job count to 1-2
- Close other applications to free memory
- Use SSD storage for input/output if possible

**For Many Small Files**
- Increase concurrent jobs to 6-8
- Enable "Use source directory" to reduce disk I/O
- Consider batch size limits (process in chunks)

**For Network Storage**
- Copy files locally before conversion
- Use wired connection over WiFi
- Consider compression impact on network bandwidth

### Getting Help

1. **Check Logs**: Review activity log in application or log files
2. **Search Issues**: Check [GitHub Issues](https://github.com/vid2aud/vid2aud-gui/issues)
3. **Report Bugs**: Create new issue with:
   - Operating system and version
   - FFmpeg version (`ffmpeg -version`)
   - Input file details and error messages
   - Application logs and screenshots

## 🤝 Contributing

We welcome contributions! Please read our contributing guidelines:

### Development Workflow

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes following code style guidelines
4. Add tests for new functionality
5. Run test suite (`pytest`)
6. Submit pull request

### Code Standards

- **Type Hints**: All functions must have type annotations
- **Documentation**: Docstrings required for public APIs
- **Testing**: Unit tests for core functionality
- **Style**: Follow Black formatting and Ruff linting rules

### Areas for Contribution

- 🌐 **Internationalization**: Additional language translations
- 🎨 **Themes**: Custom theme development
- 🧪 **Testing**: Expanded test coverage
- 📖 **Documentation**: User guides and tutorials
- 🐛 **Bug Fixes**: Issue resolution and optimization
- ✨ **Features**: New conversion options and UI improvements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FFmpeg Team**: For the powerful multimedia framework
- **Qt/PySide6**: For the excellent cross-platform GUI toolkit
- **PyInstaller**: For executable packaging capabilities
- **Contributors**: All developers who have contributed to this project

## 📊 Project Stats

- **Language**: Python 3.10+
- **Framework**: PySide6 (Qt6)
- **Architecture**: Multi-threaded with Qt signals/slots
- **Platforms**: Windows, macOS, Linux
- **Test Coverage**: >90% for core functionality
- **License**: MIT (commercial friendly)

---

**Vid2Aud** - Professional video to audio conversion made simple.

For support, feature requests, or contributions, visit our [GitHub repository](https://github.com/sammiykay/video2audio).