# AGENTS.md - CSV/XLS File Converter

Context and guidelines for AI agents working in this codebase.

## Project Overview

Python utility for converting CSV and XLS files to XLSX.
- **CLI**: `file_converter.py` (includes folder monitoring)
- **GUI**: `gui.py` (PySide6 + PyQt-Fluent-Widgets)
- **Platform**: Windows primary (required for XLS conversion), cross-platform for CSV.

## Build & Run

### Setup
```bash
pip install -r requirements.txt
```

### Execution
```bash
# GUI
python gui.py

# CLI
python file_converter.py input.csv
python file_converter.py input.xls -o output.xlsx
python file_converter.py --monitor "C:\path\to\folder" --delete-source
```

### Testing & Linting
**Current Status**: No test suite or lint config exists.
If adding tests/linting, use standard tools:
```bash
pip install pytest ruff
pytest tests/
ruff check .
```

## Architecture

```
.
├── file_converter.py   # Core logic, CLI, Watchdog monitoring
├── gui.py              # PySide6 application
└── requirements.txt    # Dependencies
```

- **XLS Conversion**: Uses `win32com.client` (Windows Script Host) via `cscript`. **Windows Only.**
- **CSV Reading**: Robust fallback strategy (UTF-8 -> Latin-1).
- **GUI**: Threaded monitoring (`MonitorThread`) communicating via Qt Signals.

## Code Style & Conventions

### Standards
- **Imports**: Stdlib -> Third-party (with `try/except` for optionals) -> Local.
- **Naming**: `snake_case` (funcs/vars), `PascalCase` (classes), `UPPER_CASE` (constants).
- **Formatting**: 4 spaces indent, ~100 char line limit.
- **Type Hints**: Mandatory in `gui.py`, optional but recommended elsewhere.

### Essential Patterns


**1. Optional Dependency Handling**
```python
try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False
```

**2. Error Handling (CLI)**
Return `None` or `False` on failure, print descriptive error.
```python
def process_file(path):
    try:
        # ... operation ...
    except Exception as e:
        print(f"Error: {e}")
        return False
```

**3. Qt Signals (GUI)**
Always use Signals for thread updates. Never touch UI from background threads.
```python
class Worker(QThread):
    progress = Signal(int)
    def run(self):
        self.progress.emit(50)
```

**4. Data Sanitization**
Always sanitize strings for XML compatibility before writing to XLSX.
```python
ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
def sanitize(val): return ILLEGAL_CHARACTERS_RE.sub('', val) if isinstance(val, str) else val
```

## Critical Constraints

1. **Windows Compatibility**: Do not remove `win32com` or VBScript logic. It's the only way to convert legacy XLS without paid libraries.
2. **Backticks**: The app handles backtick prefixes (`` `123 ``) to force text formatting in Excel. Preserve this logic.
3. **File Locking**: Folder monitoring must handle file locks. Use existing delays/retries.
4. **UI Thread**: `gui.py` must remain responsive. Long ops go to `MonitorThread`.

## Feature Implementation Guide

- **New CLI Flag**: Add to `argparse` in `file_converter.py`.
- **New GUI Page**: 
  1. Create widget class in `gui.py`.
  2. Add to `FluentWindow` in `setup_interface`.
- **New Format**: Update `convert_to_xlsx` in `file_converter.py`.

## Dependencies
- Core: `xlsxwriter`, `watchdog`
- GUI: `PySide6`, `PySide6-Fluent-Widgets`
- Optional: `pandas` (not currently used)
