import sys
import os
import time
import json
import uuid
from queue import Queue, Empty
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List

from _version import __version__

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QSystemTrayIcon,
    QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal, QSharedMemory, QObject, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QAction,
    QFont,
    QIcon,
    QPixmap,
    QPainter,
    QDesktopServices,
)

from PySide6.QtNetwork import QLocalServer, QLocalSocket

from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    FluentIcon,
    PushButton,
    PrimaryPushButton,
    SwitchButton,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    SimpleCardWidget,
    LineEdit,
    TextEdit,
    InfoBar,
    InfoBarPosition,
    ProgressRing,
    StrongBodyLabel,
    TitleLabel,
    IconWidget,
    Theme,
    setTheme,
    SmoothScrollArea,
    TransparentToolButton,
    ToolTipFilter,
    MessageBoxBase,
    ComboBox,
)

# Import converter functions
# We need to ensure we can import from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from file_converter import convert_to_xlsx, WATCHDOG_AVAILABLE

try:
    from history_util import get_history_file_path as get_shared_history_path
except ImportError:
    # Fallback if history_util is not available
    def get_shared_history_path():
        if sys.platform == "win32":
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            app_data = os.path.expanduser("~/.config")
        config_dir = os.path.join(app_data, "csv-xls-converter")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "conversion_history.json")

try:
    from context_menu import (
        register_context_menu,
        unregister_context_menu,
        is_context_menu_registered,
    )

    CONTEXT_MENU_AVAILABLE = True
except ImportError:
    CONTEXT_MENU_AVAILABLE = False

if WATCHDOG_AVAILABLE:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler


# ============================================================================
# Optimization Constants
# ============================================================================
BATCH_SIZE = 50  # Process files in batches
BATCH_DELAY = 0.1  # Seconds between batches (prevents CPU spikes)
FILE_DELAY = 0.05  # Seconds between individual files
MAX_QUEUE_SIZE = 10000  # Maximum pending files in queue
DISCOVERY_CHUNK_SIZE = 100  # Files to discover before yielding


# Config file path - use AppData for persistence across updates
def get_config_path():
    """Get config file path in user's AppData folder."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        app_data = os.path.expanduser("~/.config")

    config_dir = os.path.join(app_data, "csv-xls-converter")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "profiles.json")


CONFIG_FILE = get_config_path()

# Windows startup registry key
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "CSV-XLS-Converter"


def get_executable_path() -> str:
    """Get the path to the current executable or script."""
    if getattr(sys, "frozen", False):
        # Running as compiled executable (PyInstaller)
        return sys.executable
    else:
        # Running as script
        return os.path.abspath(sys.argv[0])


def set_auto_startup(enable: bool) -> bool:
    """Enable or disable Windows auto-startup via registry.

    Returns True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REG_KEY,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        )

        if enable:
            exe_path = get_executable_path()
            # Add quotes around path in case of spaces
            winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, STARTUP_APP_NAME)
            except FileNotFoundError:
                pass  # Already removed

        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to set auto-startup: {e}")
        return False


def is_auto_startup_enabled() -> bool:
    """Check if auto-startup is currently enabled in Windows registry."""
    if sys.platform != "win32":
        return False

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_QUERY_VALUE
        )

        try:
            winreg.QueryValueEx(key, STARTUP_APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


# ============================================================================
# Data Models
# ============================================================================
@dataclass
class ConversionHistoryItem:
    """Record of a single file conversion."""

    source_path: str
    output_path: str
    status: str  # "processing", "success", "failed", "skipped"
    timestamp: float = field(default_factory=time.time)
    error_message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversionHistoryItem":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GlobalSettings:
    """Global application settings (persisted)."""

    auto_startup: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GlobalSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SingleFileSettings:
    """Settings for single file conversion (persisted)."""

    last_input_dir: str = ""
    last_output_dir: str = ""
    remove_backticks: bool = False
    auto_detect_dates: bool = False
    delete_source: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SingleFileSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MonitorProfile:
    """Data model for a monitoring profile/preset."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Profile"
    watch_folder: str = ""
    output_folder: str = ""
    enabled: bool = False
    delete_source: bool = False
    process_existing: bool = True
    auto_detect_dates: bool = False
    file_formats: list = field(default_factory=lambda: ['csv', 'xls'])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MonitorProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ConversionHistoryManager(QObject):
    """Manages conversion history with a maximum of 20 items."""

    # Signal emitted when history changes
    history_changed = Signal()

    MAX_ITEMS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[ConversionHistoryItem] = []
        self._history_file = get_shared_history_path()
        self._load_from_disk()

    def _load_from_disk(self):
        """Load history from persistent storage."""
        if os.path.exists(self._history_file):
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._items = [
                        ConversionHistoryItem.from_dict(item) for item in data
                    ]
                    # Ensure we don't exceed max items
                    if len(self._items) > self.MAX_ITEMS:
                        self._items = self._items[: self.MAX_ITEMS]
            except (json.JSONDecodeError, IOError, KeyError) as e:
                print(f"Warning: Could not load conversion history: {e}")
                self._items = []

    def _save_to_disk(self):
        """Save history to persistent storage."""
        try:
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump([item.to_dict() for item in self._items], f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save conversion history: {e}")

    def add(self, item: ConversionHistoryItem):
        """Add a conversion record to history."""
        # Check if we're updating an existing "processing" item
        for i, existing in enumerate(self._items):
            if (
                existing.source_path == item.source_path
                and existing.status == "processing"
            ):
                self._items[i] = item
                self._save_to_disk()
                self.history_changed.emit()
                return

        # Add new item at the beginning
        self._items.insert(0, item)

        # Trim to max size
        if len(self._items) > self.MAX_ITEMS:
            self._items = self._items[: self.MAX_ITEMS]

        self._save_to_disk()
        self.history_changed.emit()

    def add_processing(self, source_path: str, output_path: str):
        """Add a file that is currently being processed."""
        self.add(
            ConversionHistoryItem(
                source_path=source_path,
                output_path=output_path,
                status="processing",
            )
        )

    def mark_success(self, source_path: str, output_path: str):
        """Mark a processing item as successfully converted."""
        self.add(
            ConversionHistoryItem(
                source_path=source_path,
                output_path=output_path,
                status="success",
            )
        )

    def mark_failed(self, source_path: str, output_path: str, error: str = ""):
        """Mark a processing item as failed."""
        self.add(
            ConversionHistoryItem(
                source_path=source_path,
                output_path=output_path,
                status="failed",
                error_message=error,
            )
        )

    def mark_skipped(self, source_path: str, output_path: str):
        """Mark a file as skipped (already exists)."""
        self.add(
            ConversionHistoryItem(
                source_path=source_path,
                output_path=output_path,
                status="skipped",
            )
        )

    def get_all(self) -> List[ConversionHistoryItem]:
        """Get all history items (reloads from disk to catch external changes)."""
        self._load_from_disk()
        return self._items.copy()


class ProfileManager:
    """Manages loading, saving, and CRUD operations for monitor profiles and settings."""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.profiles: Dict[str, MonitorProfile] = {}
        self.single_file_settings: SingleFileSettings = SingleFileSettings()
        self.global_settings: GlobalSettings = GlobalSettings()
        self.load()

    def load(self):
        """Load profiles and settings from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for profile_data in data.get("profiles", []):
                        profile = MonitorProfile.from_dict(profile_data)
                        self.profiles[profile.id] = profile
                    # Load single file settings
                    if "single_file_settings" in data:
                        self.single_file_settings = SingleFileSettings.from_dict(
                            data["single_file_settings"]
                        )
                    # Load global settings
                    if "global_settings" in data:
                        self.global_settings = GlobalSettings.from_dict(
                            data["global_settings"]
                        )
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load profiles: {e}")

    def save(self):
        """Save profiles and settings to JSON file."""
        try:
            data = {
                "profiles": [p.to_dict() for p in self.profiles.values()],
                "single_file_settings": self.single_file_settings.to_dict(),
                "global_settings": self.global_settings.to_dict(),
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save profiles: {e}")

    def update_single_file_settings(self, settings: SingleFileSettings):
        """Update single file conversion settings."""
        self.single_file_settings = settings
        self.save()

    def update_global_settings(self, settings: GlobalSettings):
        """Update global application settings."""
        self.global_settings = settings
        self.save()

    def add(self, profile: MonitorProfile) -> MonitorProfile:
        """Add a new profile."""
        self.profiles[profile.id] = profile
        self.save()
        return profile

    def update(self, profile: MonitorProfile):
        """Update an existing profile."""
        if profile.id in self.profiles:
            self.profiles[profile.id] = profile
            self.save()

    def delete(self, profile_id: str):
        """Delete a profile by ID."""
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            self.save()

    def get(self, profile_id: str) -> Optional[MonitorProfile]:
        """Get a profile by ID."""
        return self.profiles.get(profile_id)

    def get_all(self) -> List[MonitorProfile]:
        """Get all profiles."""
        return list(self.profiles.values())


class LogSignal(QThread):
    """Signal carrier for logging"""

    message = Signal(str)


# GitHub repository info for version checking
GITHUB_REPO_OWNER = "faizalindrak"
GITHUB_REPO_NAME = "csv-xls-file-converter"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"


class VersionCheckThread(QThread):
    """Thread to check for latest version on GitHub."""

    result = Signal(bool, str, str)  # success, latest_version, release_url

    def run(self):
        try:
            import urllib.request
            import json as json_module

            req = urllib.request.Request(
                GITHUB_RELEASES_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "CSV-XLS-Converter",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json_module.loads(response.read().decode("utf-8"))
                tag_name = data.get("tag_name", "")
                html_url = data.get("html_url", "")
                # Remove 'v' prefix if present (e.g., 'v0.2.9' -> '0.2.9')
                version = tag_name.lstrip("v")
                self.result.emit(True, version, html_url)
        except Exception as e:
            self.result.emit(False, str(e), "")


class MonitorThread(QThread):
    """Thread for folder monitoring with optimizations for large folders"""

    log_signal = Signal(str)
    status_signal = Signal(bool)  # True = Active, False = Inactive
    progress_signal = Signal(int, int)  # (processed, total)
    stats_signal = Signal(
        int, int, int, int, int
    )  # (discovered, converted, skipped, current_batch, total_batches)
    # History signals: source_path, output_path, status, error_message
    conversion_started = Signal(str, str)  # source, output
    conversion_finished = Signal(str, str, str, str)  # source, output, status, error

    def __init__(
        self,
        folder_path,
        output_folder,
        delete_source,
        process_existing,
        auto_detect_dates=False,
        file_formats=None,
    ):
        super().__init__()
        self.folder_path = folder_path
        self.output_folder = output_folder
        self.delete_source = delete_source
        self.process_existing = process_existing
        self.auto_detect_dates = auto_detect_dates
        self.file_formats = file_formats if file_formats is not None else ['csv', 'xls']
        self.observer = None
        self._is_running = False
        self._file_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self._processed_count = 0
        self._total_count = 0
        self._converted_count = 0  # Successfully converted
        self._skipped_count = 0  # Skipped (already exists)
        self._current_batch = 0
        self._total_batches = 0
        self._converted_cache = set()  # Cache of already converted files (for session)

    def run(self):
        if not WATCHDOG_AVAILABLE:
            self.log_signal.emit("Error: watchdog library not installed.")
            return

        if not os.path.isdir(self.folder_path):
            self.log_signal.emit(f"Error: Folder not found: {self.folder_path}")
            return

        self._is_running = True
        self.status_signal.emit(True)
        self.log_signal.emit(f"Started monitoring: {self.folder_path}")

        # Process existing files with optimized batch processing
        if self.process_existing:
            self.process_existing_files_optimized()

        # Setup Observer
        event_handler = self.create_event_handler()
        self.observer = Observer()
        self.observer.schedule(event_handler, self.folder_path, recursive=True)
        self.observer.start()

        # Process queue in batches while monitoring
        try:
            while self._is_running:
                self._process_queue_batch()
                time.sleep(0.5)
        except Exception as e:
            self.log_signal.emit(f"Error in monitor loop: {e}")
        finally:
            if self.observer:
                self.observer.stop()
                self.observer.join()
            self.status_signal.emit(False)
            self.log_signal.emit("Monitor stopped.")

    def stop(self):
        self._is_running = False

    def _discover_files_lazy(self):
        """
        Generator that yields files lazily to avoid loading all paths into memory.
        Yields in chunks for better performance.
        """
        folder = Path(self.folder_path)
        chunk = []

        for fmt in self.file_formats:
            pattern = f"**/*.{fmt}"
            try:
                for file_path in folder.glob(pattern):
                    if not self._is_running:
                        return
                    chunk.append(file_path)
                    if len(chunk) >= DISCOVERY_CHUNK_SIZE:
                        yield chunk
                        chunk = []
            except Exception as e:
                self.log_signal.emit(f"Error scanning: {e}")

        if chunk:
            yield chunk

    def process_existing_files_optimized(self):
        """Process existing files with batching and rate limiting."""
        self.log_signal.emit("Scanning for existing files...")

        # Count files first (with limit to avoid long scan)
        file_count = 0
        files_to_process = []

        for chunk in self._discover_files_lazy():
            if not self._is_running:
                return
            files_to_process.extend(chunk)
            file_count += len(chunk)

            # Log progress during discovery
            if file_count % 500 == 0:
                self.log_signal.emit(f"Found {file_count} files so far...")

        if not files_to_process:
            self.log_signal.emit("No existing files found.")
            return

        self._total_count = len(files_to_process)
        self._processed_count = 0
        self._converted_count = 0
        self._skipped_count = 0
        self._total_batches = (len(files_to_process) + BATCH_SIZE - 1) // BATCH_SIZE
        self._current_batch = 0
        self.log_signal.emit(f"Found {self._total_count} files to process")
        self._emit_stats()

        # Process in batches
        for i in range(0, len(files_to_process), BATCH_SIZE):
            if not self._is_running:
                self.log_signal.emit("Processing cancelled.")
                return

            batch = files_to_process[i : i + BATCH_SIZE]
            self._current_batch += 1
            self._emit_stats()

            for file_path in batch:
                if not self._is_running:
                    return
                self.convert_file(str(file_path))
                self._processed_count += 1
                self._emit_stats()
                time.sleep(FILE_DELAY)  # Rate limiting between files

            # Progress update after each batch
            self.progress_signal.emit(self._processed_count, self._total_count)
            self.log_signal.emit(
                f"Batch {self._current_batch}/{self._total_batches}: {self._processed_count}/{self._total_count} processed"
            )

            # Delay between batches to prevent resource exhaustion
            if i + BATCH_SIZE < len(files_to_process):
                time.sleep(BATCH_DELAY)

        self.log_signal.emit(
            f"Completed processing {self._processed_count} files ({self._converted_count} converted, {self._skipped_count} skipped)"
        )

    def _emit_stats(self):
        """Emit current stats to UI."""
        self.stats_signal.emit(
            self._total_count,
            self._converted_count,
            self._skipped_count,
            self._current_batch,
            self._total_batches,
        )

    def _process_queue_batch(self):
        """Process pending files from queue in batches."""
        processed = 0
        while processed < BATCH_SIZE and not self._file_queue.empty():
            try:
                file_path = self._file_queue.get_nowait()
                self.convert_file(file_path)
                processed += 1
                time.sleep(FILE_DELAY)
            except Empty:
                break
            except Exception as e:
                self.log_signal.emit(f"Queue processing error: {e}")

    def _enqueue_file(self, file_path):
        """Add file to processing queue with overflow protection."""
        try:
            self._file_queue.put_nowait(file_path)
        except Exception:
            self.log_signal.emit(f"Queue full, skipped: {os.path.basename(file_path)}")

    def process_existing_files(self):
        """Legacy method - redirects to optimized version."""
        self.process_existing_files_optimized()

    def create_event_handler(self):
        # We define the handler inside to access 'self' easily
        thread_ref = self
        allowed_formats = self.file_formats

        class GuiConversionHandler(FileSystemEventHandler):
            def __init__(self):
                super().__init__()
                self.processing = set()

            def _should_process(self, file_path):
                ext = os.path.splitext(file_path)[1].lower().lstrip('.')
                return ext in allowed_formats

            def _process_file(self, file_path):
                if file_path in self.processing:
                    return
                if not self._should_process(file_path):
                    return

                # Debounce/Wait for write completion
                time.sleep(0.5)

                if not os.path.exists(file_path):
                    return

                self.processing.add(file_path)
                try:
                    # Use queue for rate-limited processing
                    thread_ref._enqueue_file(file_path)
                finally:
                    self.processing.discard(file_path)

            def on_created(self, event):
                if not event.is_directory:
                    self._process_file(event.src_path)

            def on_moved(self, event):
                if not event.is_directory:
                    self._process_file(event.dest_path)

        return GuiConversionHandler()

    def convert_file(self, source_path):
        base_name = os.path.splitext(os.path.basename(source_path))[0] + ".xlsx"
        if self.output_folder:
            output_path = os.path.join(self.output_folder, base_name)
        else:
            output_path = os.path.join(os.path.dirname(source_path), base_name)

        # Skip if already processed in this session (memory cache)
        if source_path in self._converted_cache:
            return

        # Skip if xlsx already exists (filesystem check)
        if os.path.exists(output_path):
            self._converted_cache.add(source_path)  # Cache to avoid repeated fs checks
            self._skipped_count += 1
            self._emit_stats()
            self.log_signal.emit(f"Skipped (already exists): {base_name}")
            self.conversion_finished.emit(source_path, output_path, "skipped", "")
            return

        self.log_signal.emit(f"Converting: {os.path.basename(source_path)}")
        self.conversion_started.emit(source_path, output_path)

        try:
            result = convert_to_xlsx(
                source_path, output_path, auto_detect_dates=self.auto_detect_dates
            )
            if result:
                self._converted_cache.add(source_path)  # Mark as converted
                self._converted_count += 1
                self._emit_stats()
                self.log_signal.emit(f"Success: {os.path.basename(output_path)}")
                self.conversion_finished.emit(source_path, output_path, "success", "")
                if self.delete_source:
                    try:
                        os.remove(source_path)
                        self.log_signal.emit("Deleted source file")
                    except Exception as e:
                        self.log_signal.emit(f"Failed to delete source: {e}")
            else:
                self.log_signal.emit(
                    f"Failed to convert: {os.path.basename(source_path)}"
                )
                self.conversion_finished.emit(
                    source_path, output_path, "failed", "Conversion returned None"
                )
        except Exception as e:
            self.log_signal.emit(
                f"Error converting {os.path.basename(source_path)}: {e}"
            )
            self.conversion_finished.emit(source_path, output_path, "failed", str(e))


# ============================================================================
# Profile UI Components
# ============================================================================


class ProfileEditDialog(MessageBoxBase):
    """Dialog for creating/editing a monitor profile."""

    def __init__(self, parent=None, profile: MonitorProfile = None):
        super().__init__(parent)
        self.profile = profile or MonitorProfile()
        self._is_new = profile is None

        self.titleLabel = SubtitleLabel(
            "New Profile" if self._is_new else "Edit Profile", self
        )

        # Profile name
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("Profile name...")
        self.name_edit.setText(self.profile.name)
        self.name_edit.setClearButtonEnabled(True)

        # Watch folder
        watch_layout = QHBoxLayout()
        watch_layout.setSpacing(8)
        self.watch_edit = LineEdit(self)
        self.watch_edit.setPlaceholderText("Folder to monitor...")
        self.watch_edit.setText(self.profile.watch_folder)
        self.watch_btn = PushButton(FluentIcon.FOLDER, "Browse", self)
        self.watch_btn.clicked.connect(self._browse_watch)
        watch_layout.addWidget(self.watch_edit)
        watch_layout.addWidget(self.watch_btn)

        # Output folder
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        self.output_edit = LineEdit(self)
        self.output_edit.setPlaceholderText(
            "Output folder (optional, same as watch)..."
        )
        self.output_edit.setText(self.profile.output_folder)
        self.output_btn = PushButton(FluentIcon.FOLDER, "Browse", self)
        self.output_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # Options
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 8, 0, 0)

        self.process_existing_switch = SwitchButton(self)
        self.process_existing_switch.setChecked(self.profile.process_existing)
        options_layout.addWidget(self.process_existing_switch)
        options_layout.addWidget(BodyLabel("Process existing"))
        options_layout.addSpacing(12)

        self.delete_source_switch = SwitchButton(self)
        self.delete_source_switch.setChecked(self.profile.delete_source)
        options_layout.addWidget(self.delete_source_switch)
        options_layout.addWidget(BodyLabel("Delete source"))
        options_layout.addSpacing(12)

        self.auto_dates_switch = SwitchButton(self)
        self.auto_dates_switch.setChecked(self.profile.auto_detect_dates)
        options_layout.addWidget(self.auto_dates_switch)
        options_layout.addWidget(BodyLabel("Dates (β)"))
        options_layout.addStretch(1)

        # Add to view layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(StrongBodyLabel("Profile Name"))
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(StrongBodyLabel("Watch Folder"))
        self.viewLayout.addLayout(watch_layout)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(StrongBodyLabel("Output Folder (Optional)"))
        self.viewLayout.addLayout(output_layout)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(StrongBodyLabel("Options"))
        self.viewLayout.addLayout(options_layout)

        self.widget.setMinimumWidth(450)
        self.yesButton.setText("Save")
        self.cancelButton.setText("Cancel")

    def _browse_watch(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Watch Folder")
        if folder:
            self.watch_edit.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_edit.setText(folder)

    def get_profile(self) -> MonitorProfile:
        """Get the edited profile data."""
        self.profile.name = self.name_edit.text().strip() or "Unnamed Profile"
        self.profile.watch_folder = self.watch_edit.text().strip()
        self.profile.output_folder = self.output_edit.text().strip()
        self.profile.process_existing = self.process_existing_switch.isChecked()
        self.profile.delete_source = self.delete_source_switch.isChecked()
        self.profile.auto_detect_dates = self.auto_dates_switch.isChecked()
        return self.profile


class ProfileCard(SimpleCardWidget):
    """Card widget representing a single monitor profile."""

    # Signals
    toggled = Signal(str, bool)  # profile_id, enabled
    edit_requested = Signal(str)  # profile_id
    delete_requested = Signal(str)  # profile_id

    def __init__(self, profile: MonitorProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.monitor_thread: Optional[MonitorThread] = None

        self.setFixedHeight(90)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Enable/Disable switch
        self.enable_switch = SwitchButton()
        self.enable_switch.setChecked(profile.enabled)
        self.enable_switch.checkedChanged.connect(self._on_toggle)
        layout.addWidget(self.enable_switch)

        # Profile info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.name_label = StrongBodyLabel(profile.name)
        self.path_label = CaptionLabel(profile.watch_folder or "No folder set")
        self.path_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))

        # Status label
        self.status_label = CaptionLabel("Inactive")
        self.status_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.path_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout, 1)

        # Progress ring (hidden by default)
        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(20, 20)
        self.progress_ring.setStrokeWidth(3)
        self.progress_ring.hide()
        layout.addWidget(self.progress_ring)

        # Action buttons
        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(32, 32)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile.id))
        self.edit_btn.installEventFilter(ToolTipFilter(self.edit_btn, showDelay=300))
        self.edit_btn.setToolTip("Edit profile")

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(32, 32)
        self.delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(self.profile.id)
        )
        self.delete_btn.installEventFilter(
            ToolTipFilter(self.delete_btn, showDelay=300)
        )
        self.delete_btn.setToolTip("Delete profile")

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self, checked):
        self.toggled.emit(self.profile.id, checked)

    def update_profile(self, profile: MonitorProfile):
        """Update the displayed profile data."""
        self.profile = profile
        self.name_label.setText(profile.name)
        self.path_label.setText(profile.watch_folder or "No folder set")

    def set_running(self, is_running: bool):
        """Update UI to reflect running state."""
        if is_running:
            self.progress_ring.show()
            self.status_label.setText("Active")
            self.status_label.setTextColor(QColor(0, 164, 0), QColor(80, 200, 80))
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        else:
            self.progress_ring.hide()
            self.status_label.setText("Inactive")
            self.status_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

    def set_stats(self, converted: int, skipped: int):
        """Update stats display."""
        if converted > 0 or skipped > 0:
            self.status_label.setText(
                f"Active - {converted} converted, {skipped} skipped"
            )


class SingleFileConversionThread(QThread):
    """Thread for single file conversion with progress reporting."""

    progress = Signal(int)  # 0-100 percentage
    finished_signal = Signal(bool, str)  # success, result_path_or_error
    # History signals
    conversion_started = Signal(str, str)  # source, output
    conversion_finished = Signal(str, str, str, str)  # source, output, status, error

    def __init__(
        self,
        input_path: str,
        output_path: str | None,
        remove_backticks: bool,
        auto_detect_dates: bool,
        delete_source: bool,
    ):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.remove_backticks = remove_backticks
        self.auto_detect_dates = auto_detect_dates
        self.delete_source = delete_source
        self._actual_output_path = self._resolve_output_path()

    def _resolve_output_path(self) -> str:
        """Resolve output path for history entries."""
        if self.output_path:
            return self.output_path

        base_name = os.path.splitext(os.path.basename(self.input_path))[0] + ".xlsx"
        return os.path.join(os.path.dirname(self.input_path), base_name)

    def run(self):
        try:
            self.progress.emit(10)  # Started

            # Determine actual output path for history
            self._actual_output_path = self._resolve_output_path()

            self.conversion_started.emit(self.input_path, self._actual_output_path)

            result = convert_to_xlsx(
                self.input_path,
                self.output_path,
                self.remove_backticks,
                self.auto_detect_dates,
            )
            self.progress.emit(90)  # Conversion done
            if result:
                # Delete source file if option enabled
                if self.delete_source:
                    try:
                        os.remove(self.input_path)
                    except Exception as e:
                        # Conversion succeeded but deletion failed
                        self.progress.emit(100)
                        self.finished_signal.emit(
                            True, f"{result} (failed to delete original: {e})"
                        )
                        self.conversion_finished.emit(
                            self.input_path, result, "success", ""
                        )
                        return
                self.progress.emit(100)  # Done
                self.finished_signal.emit(True, result)
                self.conversion_finished.emit(self.input_path, result, "success", "")
            else:
                self.progress.emit(100)
                error_msg = "Conversion failed. Check console for details."
                self.finished_signal.emit(False, error_msg)
                self.conversion_finished.emit(
                    self.input_path, self._actual_output_path, "failed", error_msg
                )
        except Exception as e:
            self.progress.emit(100)
            self.finished_signal.emit(False, str(e))
            self.conversion_finished.emit(
                self.input_path, self._actual_output_path, "failed", str(e)
            )


class DropArea(QWidget):
    """A drop zone widget for drag-and-drop file input."""

    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self._is_dragging = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        self.icon = IconWidget(FluentIcon.DOWNLOAD)
        self.icon.setFixedSize(32, 32)

        self.label = BodyLabel("Drag & drop CSV or XLS file here")
        self.sublabel = CaptionLabel("or use Browse button below")
        self.sublabel.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))

        layout.addWidget(self.icon, alignment=Qt.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        layout.addWidget(self.sublabel, alignment=Qt.AlignCenter)

        self._update_style()

    def _update_style(self):
        border_color = "#0078d4" if self._is_dragging else "#d0d0d0"
        bg_color = "rgba(0, 120, 212, 0.05)" if self._is_dragging else "transparent"
        self.setStyleSheet(
            f"""
            DropArea {{
                border: 2px dashed {border_color};
                border-radius: 8px;
                background: {bg_color};
            }}
            """
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self._is_valid_file(urls[0].toLocalFile()):
                event.acceptProposedAction()
                self._is_dragging = True
                self._update_style()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_dragging = False
        self._update_style()

    def dropEvent(self, event):
        self._is_dragging = False
        self._update_style()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self._is_valid_file(file_path):
                self.file_dropped.emit(file_path)
                event.acceptProposedAction()
                return
        event.ignore()

    def _is_valid_file(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in [".csv", ".xls"]


class SingleFileCard(SimpleCardWidget):
    """Card for single file conversion"""

    def __init__(
        self,
        profile_manager: ProfileManager,
        history_manager: ConversionHistoryManager = None,
        parent=None,
    ):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.history_manager = history_manager
        self.conversion_thread: SingleFileConversionThread | None = None
        self.setBorderRadius(8)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(6)

        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        icon = IconWidget(FluentIcon.DOCUMENT)
        icon.setFixedSize(24, 24)
        title = SubtitleLabel("Convert Single File")
        header_layout.addWidget(icon)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.main_layout.addLayout(header_layout)

        # Drop Area for drag-and-drop
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self._on_file_dropped)
        self.main_layout.addWidget(self.drop_area)

        # Input File Section
        input_label = StrongBodyLabel("Input File")
        self.main_layout.addWidget(input_label)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        self.input_path_edit = LineEdit()
        self.input_path_edit.setPlaceholderText("Select CSV or XLS file...")
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setClearButtonEnabled(True)
        self.browse_input_btn = PushButton(FluentIcon.FOLDER, "Browse")
        self.browse_input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_path_edit)
        input_layout.addWidget(self.browse_input_btn)
        self.main_layout.addLayout(input_layout)

        # Output Folder Section
        output_label = StrongBodyLabel("Output Folder (Optional)")
        self.main_layout.addWidget(output_label)

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        self.output_path_edit = LineEdit()
        self.output_path_edit.setPlaceholderText("Same as input file location")
        self.output_path_edit.setClearButtonEnabled(True)
        self.browse_output_btn = PushButton(FluentIcon.FOLDER, "Browse")
        self.browse_output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.browse_output_btn)
        self.main_layout.addLayout(output_layout)

        # Options Section
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 2, 0, 2)
        self.remove_backticks_switch = SwitchButton()
        backtick_label = BodyLabel("Remove backticks")
        backtick_label.installEventFilter(ToolTipFilter(backtick_label, showDelay=500))
        backtick_label.setToolTip(
            "Removes leading ` character used to force text format"
        )
        options_layout.addWidget(self.remove_backticks_switch)
        options_layout.addWidget(backtick_label)
        options_layout.addSpacing(16)

        # Beta: Auto-detect dates
        self.auto_detect_dates_switch = SwitchButton()
        date_label = BodyLabel("Auto-detect dates (β)")
        date_label.installEventFilter(ToolTipFilter(date_label, showDelay=500))
        date_label.setToolTip(
            "BETA: Detect and convert date columns. Handles DD/MM/YYYY vs MM/DD/YYYY"
        )
        options_layout.addWidget(self.auto_detect_dates_switch)
        options_layout.addWidget(date_label)
        options_layout.addSpacing(16)

        # Delete original file
        self.delete_source_switch = SwitchButton()
        delete_label = BodyLabel("Delete original")
        delete_label.installEventFilter(ToolTipFilter(delete_label, showDelay=500))
        delete_label.setToolTip("⚠️ Delete original file after successful conversion")
        options_layout.addWidget(self.delete_source_switch)
        options_layout.addWidget(delete_label)
        options_layout.addStretch(1)
        self.main_layout.addLayout(options_layout)

        self.main_layout.addStretch(1)

        # Progress Section (hidden by default)
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setSpacing(8)
        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(24, 24)
        self.progress_ring.setStrokeWidth(3)
        self.progress_label = CaptionLabel("Converting...")
        self.progress_layout.addWidget(self.progress_ring)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addStretch(1)

        self.progress_widget = QWidget()
        self.progress_widget.setLayout(self.progress_layout)
        self.progress_widget.hide()
        self.main_layout.addWidget(self.progress_widget)

        # Action Button
        self.convert_btn = PrimaryPushButton(FluentIcon.SYNC, "Convert to XLSX")
        self.convert_btn.setFixedHeight(32)
        self.convert_btn.clicked.connect(self.start_conversion)
        self.main_layout.addWidget(self.convert_btn)

        # Load saved settings
        self._load_settings()

        # Connect switch changes to save settings
        self.remove_backticks_switch.checkedChanged.connect(self._save_settings)
        self.auto_detect_dates_switch.checkedChanged.connect(self._save_settings)
        self.delete_source_switch.checkedChanged.connect(self._save_settings)

    def _load_settings(self):
        """Load saved settings from profile manager."""
        settings = self.profile_manager.single_file_settings
        self.output_path_edit.setText(settings.last_output_dir)
        self.remove_backticks_switch.setChecked(settings.remove_backticks)
        self.auto_detect_dates_switch.setChecked(settings.auto_detect_dates)
        self.delete_source_switch.setChecked(settings.delete_source)

    def _save_settings(self):
        """Save current settings to profile manager."""
        settings = SingleFileSettings(
            last_input_dir=self._get_last_input_dir(),
            last_output_dir=self.output_path_edit.text(),
            remove_backticks=self.remove_backticks_switch.isChecked(),
            auto_detect_dates=self.auto_detect_dates_switch.isChecked(),
            delete_source=self.delete_source_switch.isChecked(),
        )
        self.profile_manager.update_single_file_settings(settings)

    def _get_last_input_dir(self) -> str:
        """Get directory of current input file or last used dir."""
        input_path = self.input_path_edit.text()
        if input_path and os.path.exists(input_path):
            return os.path.dirname(input_path)
        return self.profile_manager.single_file_settings.last_input_dir

    def browse_input(self):
        # Use last input directory as starting point
        start_dir = self.profile_manager.single_file_settings.last_input_dir
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            start_dir,
            "Supported Files (*.csv *.xls);;CSV Files (*.csv);;XLS Files (*.xls)",
        )
        if file_path:
            self.input_path_edit.setText(file_path)
            # Save the directory for next time
            self._save_settings()

    def browse_output(self):
        # Use last output directory or input directory as starting point
        start_dir = self.output_path_edit.text()
        if not start_dir:
            start_dir = self.profile_manager.single_file_settings.last_output_dir
        if not start_dir:
            start_dir = self._get_last_input_dir()
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", start_dir
        )
        if folder_path:
            self.output_path_edit.setText(folder_path)
            self._save_settings()

    def _on_file_dropped(self, file_path: str):
        """Handle file dropped onto the drop area."""
        self.input_path_edit.setText(file_path)
        self._save_settings()
        InfoBar.success(
            title="File Selected",
            content=os.path.basename(file_path),
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000,
        )

    def start_conversion(self):
        input_path = self.input_path_edit.text()
        if not input_path or not os.path.exists(input_path):
            InfoBar.error(
                title="Error",
                content="Please select a valid input file.",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return

        # Prevent double-click during conversion
        if self.conversion_thread and self.conversion_thread.isRunning():
            return

        output_folder = self.output_path_edit.text()
        output_path = None
        if output_folder:
            filename = os.path.splitext(os.path.basename(input_path))[0] + ".xlsx"
            output_path = os.path.join(output_folder, filename)

        remove_backticks = self.remove_backticks_switch.isChecked()
        auto_detect_dates = self.auto_detect_dates_switch.isChecked()
        delete_source = self.delete_source_switch.isChecked()

        # Show progress UI
        self._set_converting_state(True)

        # Start conversion thread
        self.conversion_thread = SingleFileConversionThread(
            input_path, output_path, remove_backticks, auto_detect_dates, delete_source
        )
        self.conversion_thread.progress.connect(self._on_conversion_progress)
        self.conversion_thread.finished_signal.connect(self._on_conversion_finished)

        # Wire up history tracking
        if self.history_manager:
            self.conversion_thread.conversion_started.connect(self._on_history_started)
            self.conversion_thread.conversion_finished.connect(
                self._on_history_finished
            )

        self.conversion_thread.start()

    def _on_history_started(self, source: str, output: str):
        """Handle conversion started for history."""
        if self.history_manager:
            self.history_manager.add_processing(source, output)

    def _on_history_finished(self, source: str, output: str, status: str, error: str):
        """Handle conversion finished for history."""
        if self.history_manager:
            if status == "success":
                self.history_manager.mark_success(source, output)
            elif status == "failed":
                self.history_manager.mark_failed(source, output, error)
            elif status == "skipped":
                self.history_manager.mark_skipped(source, output)

    def _set_converting_state(self, is_converting: bool):
        """Toggle UI state during conversion."""
        self.convert_btn.setEnabled(not is_converting)
        self.browse_input_btn.setEnabled(not is_converting)
        self.browse_output_btn.setEnabled(not is_converting)
        self.drop_area.setEnabled(not is_converting)
        self.progress_widget.setVisible(is_converting)

        if is_converting:
            self.convert_btn.setText("Converting...")
            self.progress_label.setText("Converting...")
        else:
            self.convert_btn.setText("Convert to XLSX")

    def _on_conversion_progress(self, percent: int):
        """Handle progress updates from conversion thread."""
        self.progress_label.setText(f"Converting... {percent}%")

    def _on_conversion_finished(self, success: bool, result: str):
        """Handle conversion completion."""
        self._set_converting_state(False)

        if success:
            InfoBar.success(
                title="Success",
                content=f"File converted to: {result}",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=5000,
            )
        else:
            InfoBar.error(
                title="Conversion Failed",
                content=result,
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )


class FolderMonitorCard(SimpleCardWidget):
    """Card for folder monitoring"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.monitor_thread = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(6)

        # Status indicator row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.status_ring = ProgressRing()
        self.status_ring.setFixedSize(20, 20)
        self.status_ring.setStrokeWidth(3)
        self.status_ring.hide()

        self.status_label = CaptionLabel("Inactive")
        self.status_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))

        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.status_ring)
        self.main_layout.addLayout(header_layout)

        # Stats Cards Row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        stats_row.setContentsMargins(0, 4, 0, 8)

        self.discovered_card = self._create_stat_card("Discovered", "0")
        self.converted_card = self._create_stat_card("Converted", "0")
        self.skipped_card = self._create_stat_card("Skipped", "0")
        self.batch_card = self._create_stat_card("Batch", "-/-")

        stats_row.addWidget(self.discovered_card)
        stats_row.addWidget(self.converted_card)
        stats_row.addWidget(self.skipped_card)
        stats_row.addWidget(self.batch_card)
        stats_row.addStretch(1)
        self.main_layout.addLayout(stats_row)

        # Watch Folder Section
        watch_label = StrongBodyLabel("Watch Folder")
        self.main_layout.addWidget(watch_label)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        self.input_folder_edit = LineEdit()
        self.input_folder_edit.setPlaceholderText("Select folder to monitor...")
        self.input_folder_edit.setClearButtonEnabled(True)
        self.browse_input_btn = PushButton(FluentIcon.FOLDER, "Browse")
        self.browse_input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_folder_edit)
        input_layout.addWidget(self.browse_input_btn)
        self.main_layout.addLayout(input_layout)

        # Output Folder Section
        output_label = StrongBodyLabel("Output Folder (Optional)")
        self.main_layout.addWidget(output_label)

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        self.output_folder_edit = LineEdit()
        self.output_folder_edit.setPlaceholderText("Same as source folder")
        self.output_folder_edit.setClearButtonEnabled(True)
        self.browse_output_btn = PushButton(FluentIcon.FOLDER, "Browse")
        self.browse_output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_folder_edit)
        output_layout.addWidget(self.browse_output_btn)
        self.main_layout.addLayout(output_layout)

        # Options - inline
        opt_layout = QHBoxLayout()
        opt_layout.setContentsMargins(0, 2, 0, 2)
        self.process_existing_switch = SwitchButton()
        self.process_existing_switch.setChecked(True)
        opt_layout.addWidget(self.process_existing_switch)
        opt_layout.addWidget(BodyLabel("Process existing"))
        opt_layout.addSpacing(12)
        self.delete_source_switch = SwitchButton()
        opt_layout.addWidget(self.delete_source_switch)
        delete_label = BodyLabel("Delete source")
        delete_label.installEventFilter(ToolTipFilter(delete_label, showDelay=500))
        delete_label.setToolTip("⚠️ Original files will be permanently deleted")
        opt_layout.addWidget(delete_label)
        opt_layout.addSpacing(12)

        # Beta: Auto-detect dates
        self.auto_detect_dates_switch = SwitchButton()
        opt_layout.addWidget(self.auto_detect_dates_switch)
        date_label = BodyLabel("Dates (β)")
        date_label.installEventFilter(ToolTipFilter(date_label, showDelay=500))
        date_label.setToolTip("BETA: Auto-detect and convert date columns")
        opt_layout.addWidget(date_label)
        opt_layout.addStretch(1)
        self.main_layout.addLayout(opt_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.start_btn = PrimaryPushButton(FluentIcon.PLAY, "Start")
        self.start_btn.setFixedHeight(32)
        self.start_btn.clicked.connect(self.start_monitoring)

        self.stop_btn = PushButton(FluentIcon.PAUSE, "Stop")
        self.stop_btn.setFixedHeight(32)
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addStretch(1)
        self.main_layout.addLayout(btn_layout)

        # Activity Log Section
        log_header = QHBoxLayout()
        log_label = StrongBodyLabel("Activity Log")
        self.clear_log_btn = TransparentToolButton(FluentIcon.DELETE)
        self.clear_log_btn.setFixedSize(24, 24)
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_log_btn.installEventFilter(
            ToolTipFilter(self.clear_log_btn, showDelay=300)
        )
        self.clear_log_btn.setToolTip("Clear log")
        log_header.addWidget(log_label)
        log_header.addStretch(1)
        log_header.addWidget(self.clear_log_btn)
        self.main_layout.addLayout(log_header)

        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        self.log_text.setPlaceholderText("Activity will appear here...")
        self.main_layout.addWidget(self.log_text)

    def clear_log(self):
        self.log_text.clear()

    def browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Watch Folder")
        if folder:
            self.input_folder_edit.setText(folder)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_edit.setText(folder)

    def start_monitoring(self):
        folder_path = self.input_folder_edit.text()
        if not folder_path or not os.path.exists(folder_path):
            InfoBar.error(
                title="Error",
                content="Please select a valid folder to monitor.",
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )
            return

        if not WATCHDOG_AVAILABLE:
            InfoBar.error(
                title="Missing Dependency",
                content="Watchdog library is required. Run 'pip install watchdog'",
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )
            return

        output_folder = self.output_folder_edit.text() or None
        delete_source = self.delete_source_switch.isChecked()
        process_existing = self.process_existing_switch.isChecked()
        auto_detect_dates = self.auto_detect_dates_switch.isChecked()

        # Disable inputs
        self.toggle_inputs(False)
        self.reset_stats()

        # Start Thread
        self.monitor_thread = MonitorThread(
            folder_path,
            output_folder,
            delete_source,
            process_existing,
            auto_detect_dates,
        )
        self.monitor_thread.log_signal.connect(self.append_log)
        self.monitor_thread.status_signal.connect(self.update_status)
        self.monitor_thread.stats_signal.connect(self.update_stats)
        self.monitor_thread.start()

    def stop_monitoring(self):
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.stop()
            self.append_log("Stopping monitor (please wait)...")
            self.stop_btn.setEnabled(False)
            # Thread will emit signal when actually stopped to re-enable inputs

    def toggle_inputs(self, enable):
        self.input_folder_edit.setEnabled(enable)
        self.browse_input_btn.setEnabled(enable)
        self.output_folder_edit.setEnabled(enable)
        self.browse_output_btn.setEnabled(enable)
        self.delete_source_switch.setEnabled(enable)
        self.process_existing_switch.setEnabled(enable)
        self.auto_detect_dates_switch.setEnabled(enable)
        self.start_btn.setEnabled(enable)
        self.stop_btn.setEnabled(not enable)

    def append_log(self, message):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _create_stat_card(self, label, value):
        """Create a mini stat card widget."""
        card = SimpleCardWidget()
        card.setFixedSize(90, 50)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        value_label = StrongBodyLabel(value)
        value_label.setObjectName(f"{label.lower()}_value")
        title_label = CaptionLabel(label)

        layout.addWidget(value_label, alignment=Qt.AlignCenter)
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        return card

    def _get_stat_value_label(self, card):
        """Get the value label from a stat card."""
        for child in card.findChildren(StrongBodyLabel):
            return child
        return None

    def update_status(self, is_running):
        if is_running:
            self.status_ring.show()
            self.status_label.setText("Active")
            self.status_label.setTextColor(QColor(0, 164, 0), QColor(80, 200, 80))
        else:
            self.status_ring.hide()
            self.status_label.setText("Inactive")
            self.status_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
            self.toggle_inputs(True)

    def update_stats(
        self, discovered, converted, skipped, current_batch, total_batches
    ):
        self._get_stat_value_label(self.discovered_card).setText(str(discovered))
        self._get_stat_value_label(self.converted_card).setText(str(converted))
        self._get_stat_value_label(self.skipped_card).setText(str(skipped))
        if total_batches > 0:
            self._get_stat_value_label(self.batch_card).setText(
                f"{current_batch}/{total_batches}"
            )
        else:
            self._get_stat_value_label(self.batch_card).setText("-/-")

    def reset_stats(self):
        self._get_stat_value_label(self.discovered_card).setText("0")
        self._get_stat_value_label(self.converted_card).setText("0")
        self._get_stat_value_label(self.skipped_card).setText("0")
        self._get_stat_value_label(self.batch_card).setText("-/-")


class HomePage(QWidget):
    def __init__(
        self,
        profile_manager: ProfileManager,
        history_manager: ConversionHistoryManager = None,
        parent=None,
    ):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.history_manager = history_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Title
        title_label = TitleLabel("Single File Conversion")
        layout.addWidget(title_label)

        layout.addWidget(
            CaptionLabel("Convert individual CSV or XLS files to XLSX format.")
        )

        # Card
        self.card = SingleFileCard(profile_manager, history_manager)
        layout.addWidget(self.card)
        layout.addStretch(1)


class MonitorPage(QWidget):
    """Page for managing multiple monitor profiles."""

    def __init__(
        self,
        profile_manager: ProfileManager,
        history_manager: ConversionHistoryManager = None,
        parent=None,
    ):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.history_manager = history_manager
        self.profile_cards: Dict[str, ProfileCard] = {}
        self.monitor_threads: Dict[str, MonitorThread] = {}
        self._is_shutting_down = (
            False  # Flag to prevent saving enabled=False on app close
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        title_label = TitleLabel("Folder Monitoring")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self.add_profile_btn = PrimaryPushButton(FluentIcon.ADD, "Add Profile")
        self.add_profile_btn.clicked.connect(self._add_profile)
        header_layout.addWidget(self.add_profile_btn)
        layout.addLayout(header_layout)

        layout.addWidget(
            CaptionLabel("Create profiles to monitor multiple folders simultaneously.")
        )

        # Scrollable profile list
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.profiles_layout = QVBoxLayout(self.scroll_content)
        self.profiles_layout.setContentsMargins(0, 0, 0, 0)
        self.profiles_layout.setSpacing(8)
        self.profiles_layout.addStretch(1)

        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

        # Activity Log Section
        log_header = QHBoxLayout()
        log_label = StrongBodyLabel("Activity Log")
        self.clear_log_btn = TransparentToolButton(FluentIcon.DELETE)
        self.clear_log_btn.setFixedSize(24, 24)
        self.clear_log_btn.clicked.connect(self._clear_log)
        self.clear_log_btn.installEventFilter(
            ToolTipFilter(self.clear_log_btn, showDelay=300)
        )
        self.clear_log_btn.setToolTip("Clear log")
        log_header.addWidget(log_label)
        log_header.addStretch(1)
        log_header.addWidget(self.clear_log_btn)
        layout.addLayout(log_header)

        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        self.log_text.setPlaceholderText("Activity will appear here...")
        layout.addWidget(self.log_text)

        # Load existing profiles
        self._load_profiles()

    def _load_profiles(self):
        """Load and display all saved profiles."""
        for profile in self.profile_manager.get_all():
            self._create_profile_card(profile)
            # Auto-start monitors for profiles that were enabled
            if profile.enabled:
                self._start_monitor(profile)

        # Show empty state if no profiles
        if not self.profile_cards:
            self._show_empty_state()

    def _show_empty_state(self):
        """Show empty state message."""
        # Will be hidden when first profile is added
        pass

    def _create_profile_card(self, profile: MonitorProfile) -> ProfileCard:
        """Create and add a profile card to the list."""
        card = ProfileCard(profile)
        card.toggled.connect(self._on_profile_toggled)
        card.edit_requested.connect(self._edit_profile)
        card.delete_requested.connect(self._delete_profile)

        # Insert before the stretch
        self.profiles_layout.insertWidget(self.profiles_layout.count() - 1, card)
        self.profile_cards[profile.id] = card
        return card

    def _add_profile(self):
        """Show dialog to add a new profile."""
        dialog = ProfileEditDialog(self.window())
        if dialog.exec():
            profile = dialog.get_profile()
            self.profile_manager.add(profile)
            self._create_profile_card(profile)
            self._log(f"Profile created: {profile.name}")

    def _edit_profile(self, profile_id: str):
        """Show dialog to edit an existing profile."""
        profile = self.profile_manager.get(profile_id)
        if not profile:
            return

        dialog = ProfileEditDialog(self.window(), profile)
        if dialog.exec():
            updated_profile = dialog.get_profile()
            self.profile_manager.update(updated_profile)

            # Update the card
            if profile_id in self.profile_cards:
                self.profile_cards[profile_id].update_profile(updated_profile)

            self._log(f"Profile updated: {updated_profile.name}")

    def _delete_profile(self, profile_id: str):
        """Delete a profile after confirmation."""
        profile = self.profile_manager.get(profile_id)
        if not profile:
            return

        # Stop monitoring if running
        self._stop_monitor(profile_id)

        # Remove card
        if profile_id in self.profile_cards:
            card = self.profile_cards.pop(profile_id)
            self.profiles_layout.removeWidget(card)
            card.deleteLater()

        self.profile_manager.delete(profile_id)
        self._log(f"Profile deleted: {profile.name}")

    def _on_profile_toggled(self, profile_id: str, enabled: bool):
        """Handle profile enable/disable toggle."""
        profile = self.profile_manager.get(profile_id)
        if not profile:
            return

        profile.enabled = enabled
        self.profile_manager.update(profile)

        if enabled:
            self._start_monitor(profile)
        else:
            self._stop_monitor(profile_id)

    def _start_monitor(self, profile: MonitorProfile):
        """Start monitoring for a profile."""
        if not profile.watch_folder or not os.path.isdir(profile.watch_folder):
            InfoBar.error(
                title="Invalid Folder",
                content=f"Watch folder not found: {profile.watch_folder}",
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )
            # Reset toggle
            if profile.id in self.profile_cards:
                self.profile_cards[profile.id].enable_switch.setChecked(False)
            return

        if not WATCHDOG_AVAILABLE:
            InfoBar.error(
                title="Missing Dependency",
                content="Watchdog library is required. Run 'pip install watchdog'",
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )
            if profile.id in self.profile_cards:
                self.profile_cards[profile.id].enable_switch.setChecked(False)
            return

        # Create and start monitor thread
        thread = MonitorThread(
            profile.watch_folder,
            profile.output_folder or None,
            profile.delete_source,
            profile.process_existing,
            profile.auto_detect_dates,
        )
        thread.log_signal.connect(lambda msg: self._log(f"[{profile.name}] {msg}"))
        thread.status_signal.connect(
            lambda running: self._on_monitor_status(profile.id, running)
        )
        thread.stats_signal.connect(
            lambda d, c, s, cb, tb: self._on_monitor_stats(profile.id, c, s)
        )

        # Wire up history tracking
        if self.history_manager:
            thread.conversion_started.connect(self._on_history_started)
            thread.conversion_finished.connect(self._on_history_finished)

        self.monitor_threads[profile.id] = thread
        thread.start()

        if profile.id in self.profile_cards:
            self.profile_cards[profile.id].set_running(True)

        self._log(f"Started monitoring: {profile.name}")

    def _on_history_started(self, source: str, output: str):
        """Handle conversion started for history."""
        if self.history_manager:
            self.history_manager.add_processing(source, output)

    def _on_history_finished(self, source: str, output: str, status: str, error: str):
        """Handle conversion finished for history."""
        if self.history_manager:
            if status == "success":
                self.history_manager.mark_success(source, output)
            elif status == "failed":
                self.history_manager.mark_failed(source, output, error)
            elif status == "skipped":
                self.history_manager.mark_skipped(source, output)

    def _stop_monitor(self, profile_id: str):
        """Stop monitoring for a profile."""
        if profile_id in self.monitor_threads:
            thread = self.monitor_threads[profile_id]
            if thread.isRunning():
                thread.stop()
                thread.wait(5000)  # Wait up to 5 seconds
            del self.monitor_threads[profile_id]

        if profile_id in self.profile_cards:
            self.profile_cards[profile_id].set_running(False)

    def _on_monitor_status(self, profile_id: str, is_running: bool):
        """Handle monitor status changes."""
        if profile_id in self.profile_cards:
            self.profile_cards[profile_id].set_running(is_running)

            # Only update saved state if not shutting down and monitor stopped unexpectedly
            if not is_running and not self._is_shutting_down:
                # Update toggle state
                profile = self.profile_manager.get(profile_id)
                if profile:
                    profile.enabled = False
                    self.profile_manager.update(profile)
                    self.profile_cards[profile_id].enable_switch.setChecked(False)

    def _on_monitor_stats(self, profile_id: str, converted: int, skipped: int):
        """Handle monitor stats updates."""
        if profile_id in self.profile_cards:
            self.profile_cards[profile_id].set_stats(converted, skipped)

    def _log(self, message: str):
        """Append message to activity log."""
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _clear_log(self):
        """Clear the activity log."""
        self.log_text.clear()

    def stop_all_monitors(self):
        """Stop all running monitors (called on app close)."""
        self._is_shutting_down = True  # Prevent saving enabled=False
        for profile_id in list(self.monitor_threads.keys()):
            self._stop_monitor(profile_id)


class VersionCard(SimpleCardWidget):
    """Card widget showing app version with update check."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.version_check_thread: Optional[VersionCheckThread] = None
        self._latest_version: Optional[str] = None
        self._release_url: Optional[str] = None

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Header row with title and button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Left side: title and version info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title = StrongBodyLabel("App Version")
        info_layout.addWidget(title)

        # Version row - current and latest on one line
        version_row = QHBoxLayout()
        version_row.setSpacing(8)

        current_label = CaptionLabel("Current:")
        current_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        self.current_version_label = BodyLabel(__version__)

        separator = CaptionLabel("•")
        separator.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))

        latest_label = CaptionLabel("Latest:")
        latest_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        self.latest_version_label = BodyLabel("—")

        version_row.addWidget(current_label)
        version_row.addWidget(self.current_version_label)
        version_row.addWidget(separator)
        version_row.addWidget(latest_label)
        version_row.addWidget(self.latest_version_label)
        version_row.addStretch(1)
        info_layout.addLayout(version_row)

        # Status row - shows update status and link on one line
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self.status_label = CaptionLabel("")
        self.status_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        status_row.addWidget(self.status_label)

        # Update link (hidden by default, same line as status)
        self.update_link = CaptionLabel("")
        self.update_link.setTextColor(QColor(0, 120, 212), QColor(100, 180, 255))
        self.update_link.setCursor(Qt.PointingHandCursor)
        self.update_link.hide()
        self.update_link.mousePressEvent = lambda e: self._open_release_page()
        status_row.addWidget(self.update_link)
        status_row.addStretch(1)

        info_layout.addLayout(status_row)

        header_layout.addLayout(info_layout, 1)

        # Right side: check button (accent color)
        self.check_btn = PrimaryPushButton(FluentIcon.SYNC, "Check for Updates")
        self.check_btn.clicked.connect(self._check_for_updates)
        header_layout.addWidget(self.check_btn)

        card_layout.addLayout(header_layout)

    def _check_for_updates(self):
        """Start version check in background thread."""
        if self.version_check_thread and self.version_check_thread.isRunning():
            return

        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking...")
        self.status_label.setText("")
        self.latest_version_label.setText("...")

        self.version_check_thread = VersionCheckThread()
        self.version_check_thread.result.connect(self._on_version_check_result)
        self.version_check_thread.start()

    def _on_version_check_result(
        self, success: bool, version_or_error: str, release_url: str
    ):
        """Handle version check result."""
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for Updates")

        if success:
            self._latest_version = version_or_error
            self._release_url = release_url
            self.latest_version_label.setText(version_or_error)

            # Compare versions
            if self._is_newer_version(version_or_error, __version__):
                self.status_label.setText("Update available!")
                self.status_label.setTextColor(QColor(0, 164, 0), QColor(80, 200, 80))
                # Show clickable link
                self.update_link.setText("📥 Download from GitHub →")
                self.update_link.show()
            else:
                self.status_label.setText("You're up to date ✓")
                self.status_label.setTextColor(
                    QColor(128, 128, 128), QColor(160, 160, 160)
                )
                self.update_link.hide()
        else:
            self.latest_version_label.setText("—")
            self.status_label.setText("Failed to check")
            self.status_label.setTextColor(QColor(200, 80, 80), QColor(200, 100, 100))
            self.update_link.hide()

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """Compare version strings (e.g., '0.2.10' > '0.2.9')."""
        try:
            latest_parts = [int(x) for x in latest.split(".")]
            current_parts = [int(x) for x in current.split(".")]
            # Pad with zeros if needed
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            return latest_parts > current_parts
        except ValueError:
            return False

    def _open_release_page(self):
        """Open the GitHub release page in browser."""
        if self._release_url:
            import webbrowser

            webbrowser.open(self._release_url)


class HistoryItemWidget(QWidget):
    """Widget representing a single conversion history item."""

    clicked = Signal(str)  # Emits output_path when clicked

    def __init__(self, item: ConversionHistoryItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setFixedHeight(48)
        self.setCursor(
            Qt.PointingHandCursor if item.status == "success" else Qt.ArrowCursor
        )
        self._base_style = self.styleSheet()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Status icon
        if item.status == "processing":
            self.status_icon = ProgressRing()
            self.status_icon.setFixedSize(16, 16)
            self.status_icon.setStrokeWidth(2)
        else:
            icon_map = {
                "success": FluentIcon.ACCEPT,
                "failed": FluentIcon.CLOSE,
                "skipped": FluentIcon.REMOVE,
            }
            self.status_icon = IconWidget(icon_map.get(item.status, FluentIcon.INFO))
            self.status_icon.setFixedSize(16, 16)
        layout.addWidget(self.status_icon)

        # File info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        filename = os.path.basename(item.output_path or item.source_path)
        self.name_label = BodyLabel(filename)
        self.name_label.setFont(QFont("Segoe UI", 9))

        status_text = {
            "processing": "Converting...",
            "success": "Converted",
            "failed": f"Failed: {item.error_message}"
            if item.error_message
            else "Failed",
            "skipped": "Skipped (exists)",
        }.get(item.status, item.status)

        self.status_label = CaptionLabel(status_text)
        self.status_label.setTextColor(
            self._get_status_color(item.status, light=True),
            self._get_status_color(item.status, light=False),
        )

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout, 1)

        # Time
        time_str = time.strftime("%H:%M", time.localtime(item.timestamp))
        self.time_label = CaptionLabel(time_str)
        self.time_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        layout.addWidget(self.time_label)

    def _get_status_color(self, status: str, light: bool) -> QColor:
        colors = {
            "processing": (QColor(0, 120, 212), QColor(100, 180, 255)),
            "success": (QColor(0, 164, 0), QColor(80, 200, 80)),
            "failed": (QColor(200, 50, 50), QColor(220, 100, 100)),
            "skipped": (QColor(128, 128, 128), QColor(160, 160, 160)),
        }
        return colors.get(status, (QColor(128, 128, 128), QColor(160, 160, 160)))[
            0 if light else 1
        ]

    def mousePressEvent(self, event):
        if self.item.status == "success" and self.item.output_path:
            self.clicked.emit(self.item.output_path)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if self.item.status == "success":
            self._base_style = self.styleSheet()
            self.setStyleSheet(
                "background-color: rgba(0, 0, 0, 0.05);" + self._base_style
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.item.status == "success":
            self.setStyleSheet(self._base_style)
        super().leaveEvent(event)


class TrayHistoryPanel(QWidget):
    """Popup panel showing recent conversion history."""

    quit_requested = Signal()
    show_window_requested = Signal()

    def __init__(self, history_manager: ConversionHistoryManager, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.history_manager = history_manager
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 420)

        # Main container with rounded corners
        self.container = QWidget(self)
        self.container.setObjectName("trayPanelContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = StrongBodyLabel("Recent Conversions")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        container_layout.addWidget(header)

        # Separator
        self.separator = QWidget()
        self.separator.setFixedHeight(1)
        container_layout.addWidget(self.separator)

        # Scroll area for history items
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(4, 4, 4, 4)
        self.items_layout.setSpacing(2)
        self.items_layout.addStretch(1)

        self.scroll_area.setWidget(self.items_container)
        container_layout.addWidget(self.scroll_area, 1)

        # Empty state label
        self.empty_label = BodyLabel("No recent conversions")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; padding: 40px;")
        self.items_layout.insertWidget(0, self.empty_label)

        # Footer with buttons
        footer = QWidget()
        footer.setFixedHeight(52)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(8)

        self.show_btn = PushButton(FluentIcon.HOME, "Open App")
        self.show_btn.clicked.connect(self._on_show_clicked)
        footer_layout.addWidget(self.show_btn)

        footer_layout.addStretch(1)

        self.quit_btn = PushButton(FluentIcon.POWER_BUTTON, "Quit")
        self.quit_btn.clicked.connect(self._on_quit_clicked)
        footer_layout.addWidget(self.quit_btn)

        container_layout.addWidget(footer)

        # Layout for this widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        # Listen for history changes via Qt signal (thread-safe)
        self.history_manager.history_changed.connect(self._refresh_items)

        # Initial load
        self._refresh_items()

    def _refresh_items(self):
        """Refresh the list of history items."""
        # Clear existing HistoryItemWidget instances only
        # Iterate backwards to safely remove items
        for i in range(self.items_layout.count() - 1, -1, -1):
            item = self.items_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), HistoryItemWidget):
                widget = self.items_layout.takeAt(i).widget()
                widget.deleteLater()

        items = self.history_manager.get_all()

        # Show/hide empty state
        self.empty_label.setVisible(len(items) == 0)

        # Add items after the empty label (index 1), before the stretch
        for idx, hist_item in enumerate(items):
            widget = HistoryItemWidget(hist_item)
            widget.clicked.connect(self._open_file)
            # Insert after empty_label (at index 1+idx)
            self.items_layout.insertWidget(1 + idx, widget)

    def _open_file(self, file_path: str):
        """Open the converted file."""
        if os.path.exists(file_path):
            if sys.platform == "win32":
                os.startfile(file_path)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        self.hide()

    def _on_show_clicked(self):
        self.hide()
        self.show_window_requested.emit()

    def _on_quit_clicked(self):
        self.hide()
        self.quit_requested.emit()

    def _update_theme_style(self):
        """Update styles based on current theme."""
        from qfluentwidgets import isDarkTheme

        if isDarkTheme():
            self.container.setStyleSheet(
                """
                #trayPanelContainer {
                    background-color: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 8px;
                }
                """
            )
            self.separator.setStyleSheet("background-color: #404040;")
        else:
            self.container.setStyleSheet(
                """
                #trayPanelContainer {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                }
                """
            )
            self.separator.setStyleSheet("background-color: #e0e0e0;")

    def showEvent(self, event):
        """Refresh items and update theme when panel is shown."""
        self._update_theme_style()
        self._refresh_items()
        super().showEvent(event)


class SettingsPage(QWidget):
    """Page for global application settings."""

    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title_label = TitleLabel("Settings")
        layout.addWidget(title_label)

        layout.addWidget(CaptionLabel("Configure global application settings."))

        # Settings Card
        settings_card = SimpleCardWidget()
        settings_card.setBorderRadius(8)
        card_layout = QVBoxLayout(settings_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(16)

        # Auto-startup setting
        startup_layout = QHBoxLayout()
        startup_layout.setSpacing(12)

        startup_info = QVBoxLayout()
        startup_info.setSpacing(2)
        startup_title = StrongBodyLabel("Start with Windows")
        startup_desc = CaptionLabel(
            "Automatically launch the application when Windows starts"
        )
        startup_desc.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        startup_info.addWidget(startup_title)
        startup_info.addWidget(startup_desc)
        startup_layout.addLayout(startup_info, 1)

        self.auto_startup_switch = SwitchButton()
        # Initialize from both saved setting and actual registry state
        actual_state = is_auto_startup_enabled()
        saved_state = self.profile_manager.global_settings.auto_startup
        # Sync if they differ (registry is source of truth)
        if actual_state != saved_state:
            self.profile_manager.global_settings.auto_startup = actual_state
            self.profile_manager.save()
        self.auto_startup_switch.setChecked(actual_state)
        self.auto_startup_switch.checkedChanged.connect(self._on_auto_startup_changed)
        startup_layout.addWidget(self.auto_startup_switch)

        card_layout.addLayout(startup_layout)

        # Context menu setting
        context_menu_layout = QHBoxLayout()
        context_menu_layout.setSpacing(12)

        context_menu_info = QVBoxLayout()
        context_menu_info.setSpacing(2)
        context_menu_title = StrongBodyLabel("Windows Context Menu")
        context_menu_desc = CaptionLabel(
            "Add 'Convert to XLSX' option when right-clicking CSV/XLS files"
        )
        context_menu_desc.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        context_menu_info.addWidget(context_menu_title)
        context_menu_info.addWidget(context_menu_desc)
        context_menu_layout.addLayout(context_menu_info, 1)

        self.context_menu_switch = SwitchButton()
        # Initialize from actual registry state
        if CONTEXT_MENU_AVAILABLE:
            self.context_menu_switch.setChecked(is_context_menu_registered())
            self.context_menu_switch.checkedChanged.connect(
                self._on_context_menu_changed
            )
        else:
            self.context_menu_switch.setEnabled(False)
        context_menu_layout.addWidget(self.context_menu_switch)

        card_layout.addLayout(context_menu_layout)

        # Windows 11 note
        if sys.platform == "win32":
            win11_note = CaptionLabel(
                "Tip: On Windows 11, use Shift+Right-click to see the menu directly"
            )
            win11_note.setTextColor(QColor(100, 100, 100), QColor(140, 140, 140))
            card_layout.addWidget(win11_note)

        # Platform note for non-Windows
        if sys.platform != "win32":
            note_label = CaptionLabel(
                "Note: Auto-startup and context menu are only available on Windows"
            )
            note_label.setTextColor(QColor(200, 150, 50), QColor(200, 150, 50))
            card_layout.addWidget(note_label)
            self.auto_startup_switch.setEnabled(False)
            self.context_menu_switch.setEnabled(False)

        layout.addWidget(settings_card)

        # Appearance Card
        appearance_card = SimpleCardWidget()
        appearance_card.setBorderRadius(8)
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(16, 16, 16, 16)
        appearance_layout.setSpacing(16)

        # Theme setting
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(12)

        theme_info = QVBoxLayout()
        theme_info.setSpacing(2)
        theme_title = StrongBodyLabel("Theme")
        theme_desc = CaptionLabel("Choose application color theme")
        theme_desc.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        theme_info.addWidget(theme_title)
        theme_info.addWidget(theme_desc)
        theme_layout.addLayout(theme_info, 1)

        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        self.theme_combo.setFixedWidth(120)
        # Set current theme selection
        from qfluentwidgets import qconfig

        current_theme = qconfig.theme
        if current_theme == Theme.AUTO:
            self.theme_combo.setCurrentIndex(0)
        elif current_theme == Theme.LIGHT:
            self.theme_combo.setCurrentIndex(1)
        else:
            self.theme_combo.setCurrentIndex(2)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)

        appearance_layout.addLayout(theme_layout)

        layout.addWidget(appearance_card)

        # Version Card
        self.version_card = VersionCard()
        layout.addWidget(self.version_card)

        # Credits Card
        credits_card = SimpleCardWidget()
        credits_card.setBorderRadius(8)
        credits_layout = QVBoxLayout(credits_card)
        credits_layout.setContentsMargins(16, 16, 16, 16)
        credits_layout.setSpacing(8)

        credits_title = StrongBodyLabel("About")
        credits_layout.addWidget(credits_title)

        copyright_label = CaptionLabel("Copyright 2026 - Faizal Kusmawan")
        copyright_label.setTextColor(QColor(128, 128, 128), QColor(160, 160, 160))
        credits_layout.addWidget(copyright_label)

        layout.addWidget(credits_card)
        layout.addStretch(1)

    def _on_auto_startup_changed(self, checked: bool):
        """Handle auto-startup toggle."""
        success = set_auto_startup(checked)
        if success:
            self.profile_manager.global_settings.auto_startup = checked
            self.profile_manager.save()
            InfoBar.success(
                title="Settings Updated",
                content=f"Auto-startup {'enabled' if checked else 'disabled'}",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )
        else:
            # Revert the switch if failed
            self.auto_startup_switch.setChecked(not checked)
            InfoBar.error(
                title="Error",
                content="Failed to update auto-startup setting",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )

    def _on_context_menu_changed(self, checked: bool):
        """Handle context menu registration toggle."""
        if not CONTEXT_MENU_AVAILABLE:
            self.context_menu_switch.setChecked(not checked)
            return

        if checked:
            success, message = register_context_menu()
        else:
            success, message = unregister_context_menu()

        if success:
            InfoBar.success(
                title="Context Menu Updated",
                content=f"Context menu {'enabled' if checked else 'disabled'}",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )
        else:
            # Revert the switch if failed
            self.context_menu_switch.setChecked(not checked)
            InfoBar.error(
                title="Error",
                content=message,
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )

    def _on_theme_changed(self, index: int):
        """Handle theme dropdown change."""
        themes = [Theme.AUTO, Theme.LIGHT, Theme.DARK]
        setTheme(themes[index])


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"CSV/XLS to XLSX Converter v{__version__}")
        self.resize(850, 650)

        # Flag to track if we're actually quitting
        self._is_quitting = False

        # System tray icon (initialized later if available)
        self.tray_icon = None
        self.tray_history_panel = None
        self._tray_base_icon = None
        self._tray_animation_timer = None
        self._tray_animation_angle = 0
        self._active_conversions = 0

        # Conversion history manager (shared across all conversion sources)
        self.history_manager = ConversionHistoryManager()

        # Connect to history changes for tray animation
        self.history_manager.history_changed.connect(self._update_tray_animation)

        # Theme - Auto detect system theme
        setTheme(Theme.AUTO)

        # Shared profile manager for all pages
        self.profile_manager = ProfileManager()

        # Pages
        self.home_page = HomePage(self.profile_manager, self.history_manager, self)
        self.home_page.setObjectName("home")

        self.monitor_page = MonitorPage(
            self.profile_manager, self.history_manager, self
        )
        self.monitor_page.setObjectName("monitor")

        self.settings_page = SettingsPage(self.profile_manager, self)
        self.settings_page.setObjectName("settings")

        # Navigation - Top items
        self.addSubInterface(
            self.home_page,
            FluentIcon.DOCUMENT,
            "Convert File",
            NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.monitor_page,
            FluentIcon.FOLDER,
            "Monitor Folder",
            NavigationItemPosition.TOP,
        )

        # Navigation - Bottom items
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "Settings",
            NavigationItemPosition.BOTTOM,
        )

        self.switchTo(self.home_page)

        # Enable Mica effect (Windows 11) for translucent background
        self.setMicaEffectEnabled(True)

        # Set custom background color as fallback
        self.setCustomBackgroundColor(
            QColor(251, 251, 251),  # Light mode
            QColor(32, 32, 32),  # Dark mode
        )

        # Center on screen
        desktop = QApplication.primaryScreen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # Setup system tray
        self._setup_system_tray()

    def _setup_system_tray(self):
        """Setup system tray icon and menu."""
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)

        # Use app icon or fallback to a built-in icon
        icon = self.windowIcon()
        if icon.isNull():
            # Use FluentIcon as fallback
            icon = FluentIcon.SYNC.icon()
        self._tray_base_icon = icon
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(f"CSV/XLS Converter v{__version__}")

        # Setup animation timer
        self._tray_animation_timer = QTimer(self)
        self._tray_animation_timer.timeout.connect(self._animate_tray_icon)

        # Create tray menu (right-click)
        tray_menu = QMenu()

        # Show action
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Create history panel (shown on single click)
        self.tray_history_panel = TrayHistoryPanel(self.history_manager)
        self.tray_history_panel.quit_requested.connect(self._quit_app)
        self.tray_history_panel.show_window_requested.connect(self._show_window)

        # Handle tray activation (single click shows panel, double click shows window)
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - show history panel near tray icon
            self._show_history_panel()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double click - show main window
            self._show_window()

    def _show_history_panel(self):
        """Show the history panel near the system tray."""
        if not self.tray_history_panel:
            return

        # Get tray icon geometry to position the panel
        tray_geometry = self.tray_icon.geometry()

        # Position panel above/near the tray icon
        panel_width = self.tray_history_panel.width()
        panel_height = self.tray_history_panel.height()

        # Get screen geometry
        screen = QApplication.primaryScreen().availableGeometry()

        # Calculate position - try to place above/near the tray
        if tray_geometry.isValid() and not tray_geometry.isNull():
            x = tray_geometry.x() - panel_width // 2 + tray_geometry.width() // 2
            y = tray_geometry.y() - panel_height - 10
        else:
            # Fallback: bottom right of screen
            x = screen.right() - panel_width - 20
            y = screen.bottom() - panel_height - 60

        # Keep panel within screen bounds
        x = max(screen.left() + 10, min(x, screen.right() - panel_width - 10))
        y = max(screen.top() + 10, min(y, screen.bottom() - panel_height - 10))

        self.tray_history_panel.move(x, y)
        self.tray_history_panel.show()
        self.tray_history_panel.activateWindow()

    def _show_window(self):
        """Show and activate the main window."""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        """Actually quit the application."""
        self._is_quitting = True
        if self._tray_animation_timer:
            self._tray_animation_timer.stop()
        self.close()

    def _update_tray_animation(self):
        """Check if any conversions are in progress and update animation state."""
        if not self.tray_icon:
            return

        items = self.history_manager.get_all()
        processing_count = sum(1 for item in items if item.status == "processing")

        if processing_count > 0 and not self._tray_animation_timer.isActive():
            # Start animation
            self._tray_animation_angle = 0
            self._tray_animation_timer.start(100)  # Update every 100ms
        elif processing_count == 0 and self._tray_animation_timer.isActive():
            # Stop animation and restore original icon
            self._tray_animation_timer.stop()
            if self._tray_base_icon:
                self.tray_icon.setIcon(self._tray_base_icon)

    def _animate_tray_icon(self):
        """Animate the tray icon by rotating it."""
        if not self.tray_icon or not self._tray_base_icon:
            return

        self._tray_animation_angle = (self._tray_animation_angle + 30) % 360

        # Get the base icon pixmap
        size = 32  # Standard tray icon size
        base_pixmap = self._tray_base_icon.pixmap(size, size)

        # Create rotated pixmap
        rotated_pixmap = QPixmap(size, size)
        rotated_pixmap.fill(Qt.transparent)

        painter = QPainter(rotated_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Translate to center, rotate, translate back
        painter.translate(size / 2, size / 2)
        painter.rotate(self._tray_animation_angle)
        painter.translate(-size / 2, -size / 2)

        painter.drawPixmap(0, 0, base_pixmap)
        painter.end()

        # Set the rotated icon
        self.tray_icon.setIcon(QIcon(rotated_pixmap))

    def closeEvent(self, event):
        """Minimize to tray instead of closing, unless quitting or tray unavailable."""
        if self._is_quitting or self.tray_icon is None:
            # Actually close - stop monitors and quit
            self.monitor_page.stop_all_monitors()
            if self.tray_icon is not None:
                self.tray_icon.hide()
            super().closeEvent(event)
        else:
            # Minimize to tray
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "CSV/XLS Converter",
                "Application minimized to tray. Folder monitoring continues in background.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )


class SingleInstanceManager:
    """Ensures only one instance of the application runs at a time."""

    APP_KEY = "csv-xls-converter-single-instance"

    def __init__(self):
        self._shared_memory = QSharedMemory(self.APP_KEY)
        self._local_server: Optional[QLocalServer] = None
        self._is_primary = False

    def try_start(self) -> bool:
        """Try to become the primary instance.

        Returns True if this is the primary instance, False if another is running.
        """
        # Try to attach to existing shared memory (another instance exists)
        if self._shared_memory.attach():
            self._shared_memory.detach()
            return False

        # Try to create shared memory (we are the primary instance)
        if self._shared_memory.create(1):
            self._is_primary = True
            self._start_server()
            return True

        # Edge case: shared memory exists but we couldn't attach
        # This can happen if previous instance crashed
        # Try to clean up and create again
        self._shared_memory.attach()
        self._shared_memory.detach()
        if self._shared_memory.create(1):
            self._is_primary = True
            self._start_server()
            return True

        return False

    def _start_server(self):
        """Start local server to listen for activation requests."""
        # Remove any stale socket
        QLocalServer.removeServer(self.APP_KEY)

        self._local_server = QLocalServer()
        self._local_server.newConnection.connect(self._on_new_connection)
        self._local_server.listen(self.APP_KEY)

    def _on_new_connection(self):
        """Handle connection from another instance trying to start."""
        if self._local_server:
            socket = self._local_server.nextPendingConnection()
            if socket:
                socket.waitForReadyRead(1000)
                socket.disconnectFromServer()
                # Bring existing window to front
                self._activate_window()

    def _activate_window(self):
        """Bring the main window to the foreground."""
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if isinstance(widget, MainWindow):
                    widget.showNormal()
                    widget.activateWindow()
                    widget.raise_()
                    break

    def notify_existing_instance(self):
        """Send activation signal to existing instance."""
        socket = QLocalSocket()
        socket.connectToServer(self.APP_KEY)
        if socket.waitForConnected(1000):
            socket.write(b"activate")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()

    def cleanup(self):
        """Clean up resources."""
        if self._local_server:
            self._local_server.close()
        if self._is_primary:
            self._shared_memory.detach()


def run_silent_conversion(file_path: str) -> int:
    """
    Run a silent conversion (for context menu integration).

    Converts the file and shows a Windows notification with the result.
    No GUI window is shown.

    Returns:
        0 on success, 1 on failure
    """
    if not os.path.exists(file_path):
        # Show error notification
        try:
            from context_menu import show_windows_notification

            show_windows_notification(
                "Conversion Failed",
                f"File not found: {os.path.basename(file_path)}",
                "error",
            )
        except ImportError:
            pass
        return 1

    # Check file extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in [".csv", ".xls"]:
        try:
            from context_menu import show_windows_notification

            show_windows_notification(
                "Conversion Failed", f"Unsupported file type: {ext}", "error"
            )
        except ImportError:
            pass
        return 1

    # Perform conversion
    try:
        result = convert_to_xlsx(file_path)
        if result:
            # Success notification
            try:
                from context_menu import show_windows_notification

                show_windows_notification(
                    "Conversion Complete",
                    f"Created: {os.path.basename(result)}",
                    "info",
                )
            except ImportError:
                pass
            return 0
        else:
            # Failed notification
            try:
                from context_menu import show_windows_notification

                show_windows_notification(
                    "Conversion Failed",
                    f"Could not convert: {os.path.basename(file_path)}",
                    "error",
                )
            except ImportError:
                pass
            return 1
    except Exception as e:
        try:
            from context_menu import show_windows_notification

            show_windows_notification("Conversion Failed", str(e), "error")
        except ImportError:
            pass
        return 1


def main():
    # Check for --silent flag (context menu invocation)
    # Parse before QApplication to avoid creating a GUI
    if len(sys.argv) >= 3 and sys.argv[1] == "--silent":
        file_path = sys.argv[2]
        exit_code = run_silent_conversion(file_path)
        sys.exit(exit_code)

    # Enable high DPI scaling for crisp fonts on high resolution displays
    # Must be called before QApplication is created
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Set application font with larger size for better readability on high DPI
    font = QFont("Segoe UI", 10)  # Increased from default ~9pt
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    # Single instance check
    instance_manager = SingleInstanceManager()
    if not instance_manager.try_start():
        # Another instance is running, notify it and exit
        instance_manager.notify_existing_instance()
        sys.exit(0)

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    instance_manager.cleanup()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
