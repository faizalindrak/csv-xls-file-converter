import sys
import os
import time
from threading import Thread
from queue import Queue, Empty
from collections import deque
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QColor

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
    ElevatedCardWidget,
    SimpleCardWidget,
    LineEdit,
    TextEdit,
    InfoBar,
    InfoBarPosition,
    ProgressRing,
    StateToolTip,
    StrongBodyLabel,
    TitleLabel,
    IconWidget,
    Theme,
    setTheme,
    ThemeColor,
    isDarkTheme,
    SmoothScrollArea,
    TransparentToolButton,
    ToolTipFilter,
    ToolTipPosition,
    toggleTheme,
)

# Import converter functions
# We need to ensure we can import from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from file_converter import convert_to_xlsx, WATCHDOG_AVAILABLE

if WATCHDOG_AVAILABLE:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent


# ============================================================================
# Optimization Constants
# ============================================================================
BATCH_SIZE = 50  # Process files in batches
BATCH_DELAY = 0.1  # Seconds between batches (prevents CPU spikes)
FILE_DELAY = 0.05  # Seconds between individual files
MAX_QUEUE_SIZE = 10000  # Maximum pending files in queue
DISCOVERY_CHUNK_SIZE = 100  # Files to discover before yielding


class LogSignal(QThread):
    """Signal carrier for logging"""

    message = Signal(str)


class MonitorThread(QThread):
    """Thread for folder monitoring with optimizations for large folders"""

    log_signal = Signal(str)
    status_signal = Signal(bool)  # True = Active, False = Inactive
    progress_signal = Signal(int, int)  # (processed, total)
    stats_signal = Signal(
        int, int, int, int, int
    )  # (discovered, converted, skipped, current_batch, total_batches)

    def __init__(
        self,
        folder_path,
        output_folder,
        delete_source,
        process_existing,
        auto_detect_dates=False,
    ):
        super().__init__()
        self.folder_path = folder_path
        self.output_folder = output_folder
        self.delete_source = delete_source
        self.process_existing = process_existing
        self.auto_detect_dates = auto_detect_dates
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

        for pattern in ["**/*.csv", "**/*.xls"]:
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
        except:
            self.log_signal.emit(f"Queue full, skipped: {os.path.basename(file_path)}")

    def process_existing_files(self):
        """Legacy method - redirects to optimized version."""
        self.process_existing_files_optimized()

    def create_event_handler(self):
        # We define the handler inside to access 'self' easily
        thread_ref = self

        class GuiConversionHandler(FileSystemEventHandler):
            def __init__(self):
                super().__init__()
                self.processing = set()

            def _should_process(self, file_path):
                ext = os.path.splitext(file_path)[1].lower()
                return ext in [".csv", ".xls"]

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
            return

        self.log_signal.emit(f"Converting: {os.path.basename(source_path)}")

        try:
            result = convert_to_xlsx(
                source_path, output_path, auto_detect_dates=self.auto_detect_dates
            )
            if result:
                self._converted_cache.add(source_path)  # Mark as converted
                self._converted_count += 1
                self._emit_stats()
                self.log_signal.emit(f"Success: {os.path.basename(output_path)}")
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
        except Exception as e:
            self.log_signal.emit(
                f"Error converting {os.path.basename(source_path)}: {e}"
            )


class SingleFileCard(ElevatedCardWidget):
    """Card for single file conversion with elevated shadow effect"""

    def __init__(self, parent=None):
        super().__init__(parent)
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
        options_layout.addStretch(1)
        self.main_layout.addLayout(options_layout)

        self.main_layout.addStretch(1)

        # Action Button
        self.convert_btn = PrimaryPushButton(FluentIcon.SYNC, "Convert to XLSX")
        self.convert_btn.setFixedHeight(32)
        self.convert_btn.clicked.connect(self.start_conversion)
        self.main_layout.addWidget(self.convert_btn)

    def browse_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Supported Files (*.csv *.xls);;CSV Files (*.csv);;XLS Files (*.xls)",
        )
        if file_path:
            self.input_path_edit.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder_path:
            self.output_path_edit.setText(folder_path)

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

        output_folder = self.output_path_edit.text()
        output_path = None
        if output_folder:
            filename = os.path.splitext(os.path.basename(input_path))[0] + ".xlsx"
            output_path = os.path.join(output_folder, filename)

        remove_backticks = self.remove_backticks_switch.isChecked()
        auto_detect_dates = self.auto_detect_dates_switch.isChecked()

        try:
            result = convert_to_xlsx(
                input_path, output_path, remove_backticks, auto_detect_dates
            )
            if result:
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
                    content="Check console logs for details.",
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                )
        except Exception as e:
            InfoBar.error(
                title="Error",
                content=str(e),
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )


class FolderMonitorCard(ElevatedCardWidget):
    """Card for folder monitoring with elevated shadow effect"""

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
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.card = SingleFileCard()
        layout.addWidget(self.card)
        layout.addStretch(1)


class MonitorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Title
        title_label = TitleLabel("Folder Monitoring")
        layout.addWidget(title_label)

        layout.addWidget(
            CaptionLabel("Automatically convert files dropped into a folder.")
        )

        # Card
        self.card = FolderMonitorCard()
        layout.addWidget(self.card)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV/XLS to XLSX Converter")
        self.resize(850, 650)

        # Theme - Auto detect system theme
        setTheme(Theme.AUTO)

        # Pages
        self.home_page = HomePage(self)
        self.home_page.setObjectName("home")

        self.monitor_page = MonitorPage(self)
        self.monitor_page.setObjectName("monitor")

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

        # Navigation - Bottom items (theme toggle)
        self.navigationInterface.addItem(
            routeKey="theme",
            icon=FluentIcon.CONSTRACT,
            text="Toggle Theme",
            onClick=self.toggle_theme,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
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

    def toggle_theme(self):
        toggleTheme(lazy=True)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
