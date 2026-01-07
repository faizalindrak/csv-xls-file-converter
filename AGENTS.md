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

### Building Releases
```bash
# Build portable exe only
build.bat

# Build portable exe + Windows installer
build.bat full
```

**Requirements for building:**
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6.x: https://jrsoftware.org/isinfo.php

**Build outputs:**
- `dist/CSV-XLS-Converter-{version}-Portable.exe` - Standalone executable
- `dist/CSV-XLS-Converter-Setup-{version}.exe` - Windows installer

### CI/CD (GitHub Actions)
Workflow: `.github/workflows/build.yml`
- **Trigger**: Push tag `v*` (e.g., `v0.2.3`) or manual dispatch
- **Outputs**: Portable exe + Installer uploaded to GitHub Release
- **Process**: PyInstaller build → Inno Setup packaging → Release creation

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
├── file_converter.py       # Core conversion logic, CLI, Watchdog monitoring
├── gui.py                  # PySide6 application with Fluent UI
├── _version.py             # Single source of truth for version
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Development dependencies
├── CSV-XLS-Converter.spec  # PyInstaller build specification
├── installer.iss           # Inno Setup installer script
├── build.bat               # Local build automation script
└── .github/workflows/
    └── build.yml           # GitHub Actions CI/CD workflow
```

- **XLS Conversion**: Uses `win32com.client` (Windows Script Host) via `cscript`. **Windows Only.**
- **CSV Reading**: Robust fallback strategy (UTF-8 -> Latin-1).
- **GUI**: Threaded monitoring (`MonitorThread`) communicating via Qt Signals.
- **Config Storage**: `%APPDATA%/csv-xls-converter/profiles.json`

## Configuration Persistence

Settings are stored in `%APPDATA%/csv-xls-converter/profiles.json`:

```json
{
  "profiles": [
    {
      "id": "uuid",
      "name": "Profile Name",
      "watch_folder": "C:\\input",
      "output_folder": "C:\\output",
      "enabled": true,
      "delete_source": false,
      "process_existing": true,
      "auto_detect_dates": false
    }
  ],
  "single_file_settings": {
    "last_input_dir": "C:\\Documents",
    "last_output_dir": "C:\\Output",
    "remove_backticks": false,
    "auto_detect_dates": true
  }
}
```

**Key classes:**
- `ProfileManager`: Handles CRUD operations and persistence
- `MonitorProfile`: Dataclass for folder monitoring profiles
- `SingleFileSettings`: Dataclass for single file conversion preferences

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

**5. Settings Persistence**
Use `ProfileManager` for all config changes. Always call `save()` after modifications.
```python
self.profile_manager.update(profile)  # Automatically saves
self.profile_manager.update_single_file_settings(settings)  # Automatically saves
```

## Critical Constraints

1. **Windows Compatibility**: Do not remove `win32com` or VBScript logic. It's the only way to convert legacy XLS without paid libraries.
2. **Backticks**: The app handles backtick prefixes (`` `123 ``) to force text formatting in Excel. Preserve this logic.
3. **File Locking**: Folder monitoring must handle file locks. Use existing delays/retries.
4. **UI Thread**: `gui.py` must remain responsive. Long ops go to `MonitorThread`.
5. **Version Sync**: Update version in both `_version.py` and `installer.iss` (CI handles this automatically on tag push).

## Feature Implementation Guide

- **New CLI Flag**: Add to `argparse` in `file_converter.py`.
- **New GUI Page**: 
  1. Create widget class in `gui.py`.
  2. Add to `FluentWindow` in `setup_interface`.
- **New Format**: Update `convert_to_xlsx` in `file_converter.py`.
- **New Setting**: Add field to `SingleFileSettings` or `MonitorProfile` dataclass, update `ProfileManager.save/load`.

## Release Process

1. Update `CHANGELOG.md` with new version section
2. Update version in `_version.py` (installer.iss is updated automatically by CI)
3. Commit changes
4. Create and push tag:
   ```bash
   git tag v0.2.4
   git push origin v0.2.4
   ```
5. GitHub Actions builds and creates release with changelog notes

## Dependencies
- Core: `xlsxwriter`, `watchdog`
- GUI: `PySide6`, `PySide6-Fluent-Widgets`
- Build: `pyinstaller` (dev only)
- Optional: `pandas` (not currently used)
