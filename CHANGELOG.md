# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.4.24] - 2026-06-24

### Changed
- Release builds now use the Rust workspace with Slint GUI and Rust CLI executables instead of PyInstaller.
- GitHub Actions and `build.bat` now build and package Cargo release artifacts.

### Added
- Native Browse buttons for GUI file and folder path fields in single-file conversion and monitor profile setup.

### Fixed
- Rust GUI drag-and-drop now accepts CSV, XLS, and XLSX files in the single-file conversion screen.
- Rust GUI executable now uses the Windows GUI subsystem so opening the app no longer shows a console window first.
- Light-theme path fields and primary actions now use higher-contrast controls in the Slint interface.

## [0.4.23] - 2026-06-24

### Fixed
- Preserve `NAN`, `INF`, and `-INF` CSV values as text so XLSX conversion no longer fails in XlsxWriter

## [0.4.22] - 2026-02-06

### Added
- Folder monitoring: exclude keywords field in GUI profiles (skip conversion for matching filenames)
- CLI monitoring: new `--exclude "kw1,kw2"` flag to skip files by filename keyword

## [0.4.21] - 2026-01-26

### Added
- File format filter checkboxes (CSV/XLS) in folder monitor profiles
- Per-profile format selection persisted to settings
- Format filter applied to both new file detection and existing file discovery

### Fixed
- Remove unused `pytest` imports in test files (ruff linting)

### Changed
- Format checkboxes disabled during active monitoring to prevent mid-session changes

## [0.4.20] - 2026-01-12

### Added
- Persistent conversion history shared between CLI and GUI
- Context menu conversions now appear in system tray history panel
- New `history_util.py` module for Qt-independent history management

### Changed
- History is now saved to disk and survives app restarts
- GUI reloads history from disk to catch external (CLI/context menu) conversions

## [0.4.19] - 2026-01-10

### Fixed
- Context menu now actually converts files instead of just opening the app
- Silent conversion mode with Windows toast notifications for results

### Changed
- Context menu appears at top position in Windows 10 classic menu
- Added Shift+Right-click tip in Settings for Windows 11 users

## [0.4.18] - 2026-01-10

### Added
- Windows Explorer context menu integration for CSV and XLS files
- Settings toggle to enable or disable the context menu entries

### Changed
- Silent CLI mode with toast notifications for context menu conversions

## [0.4.17] - 2026-01-09

### Fixed
- Harden installer to detect and close running app before updating
- Add force-close option when app cannot be closed gracefully
- Prevent "not responding" state during updates with running app

## [0.4.16] - 2026-01-09

### Fixed
- Escape formula-like CSV values to prevent Excel formula injection
- Truncate overly long cell values to Excel's maximum length

## [0.4.15] - 2026-01-09

### Fixed
- Preserve leading zeros in CSV values when converting to XLSX

## [0.4.14] - 2026-01-09

### Fixed
- Ensure history output path is resolved consistently
- Open converted files from tray history on non-Windows platforms
- Preserve history item hover styling without clobbering theme styles

## [0.4.13] - 2026-01-09

### Added
- System tray history panel showing last 20 conversions
- Single-click tray icon to view recent conversion history
- Click converted files in history panel to open them directly
- Animated (spinning) tray icon during active conversions
- "Open App" and "Quit" buttons in history panel footer
- Dark/light theme support for history panel

### Changed
- Double-click tray icon now opens main window (previously single-click)
- Right-click menu still available with Show/Quit options

## [0.3.12] - 2026-01-09

### Added
- High DPI scaling support for crisp font rendering on high resolution displays
- Improved font configuration with full hinting for sharper text

### Changed
- Increased default font size from ~9pt to 10pt for better readability

## [0.3.11] - 2026-01-08

### Added
- Single instance enforcement - only one app instance can run at a time
- When launching a second instance, the existing window is brought to front

### Fixed
- Prevented duplicate app instances running in background/system tray

## [0.3.10] - 2026-01-08

### Added
- App Version card in Settings page showing current and latest version
- "Check for Updates" button to check for new releases on GitHub
- Clickable link to download updates from GitHub releases page
- Background version checking using GitHub API

## [0.2.9] - 2026-01-08

### Added
- System tray support - app minimizes to tray instead of closing
- Tray context menu with Show and Quit options
- Double-click tray icon to restore window
- Notification balloon when minimized to tray

### Changed
- All cards now use SimpleCardWidget (no bouncing hover animation)

## [0.2.8] - 2026-01-08

### Added
- Credits section in Settings page with copyright information

### Fixed
- Disabled bouncing hover animation on Settings page cards

## [0.2.7] - 2026-01-08

### Added
- "Delete original" option for single file conversion
- Theme selection dropdown in Settings (System, Light, Dark)

### Changed
- Moved theme toggle from navigation bar to Settings page
- Separated Settings page into distinct cards for better organization
- Disabled hover effects on Settings cards for cleaner appearance

## [0.2.6] - 2026-01-08

### Added
- Drag-and-drop support in single file conversion mode
- Visual drop zone with hover feedback for file selection
- Progress indicator during single file conversion
- Background thread for non-blocking file conversion

### Changed
- Single file conversion now runs in background thread, keeping UI responsive
- Convert button shows "Converting..." state during operation
- UI elements disabled during conversion to prevent double-clicks

## [0.2.5] - 2026-01-07

### Added
- Settings page with global application settings
- Auto-startup option to launch app with Windows
- Windows registry integration for startup management

### Fixed
- Profile enabled state now persists correctly across app restarts

## [0.2.4] - 2026-01-07

### Added
- Updated AGENTS.md with comprehensive build, CI/CD, and configuration documentation

### Fixed
- Auto-start folder monitors for previously enabled profiles on app launch

## [0.2.3] - 2026-01-07

### Added
- Persist single file conversion settings (remove_backticks, auto_detect_dates)
- Remember last used input/output directories in file dialogs
- Settings saved to `%APPDATA%\csv-xls-converter\profiles.json`
- `SingleFileSettings` dataclass for storing conversion preferences
- Shared `ProfileManager` instance between HomePage and MonitorPage

### Fixed
- Auto-start monitors for previously enabled profiles on app launch

## [0.2.2] - 2026-01-07

### Added
- Windows installer build with Inno Setup
- GitHub Actions CI/CD workflow for automated builds
- `build.bat` for local build automation
- `installer.iss` Inno Setup script
- Produces both portable exe and installer on tag push

### Changed
- Updated `.gitignore` to include PyInstaller spec file

## [0.2.1] - 2026-01-06

### Added
- Initial release with GUI and CLI
- CSV to XLSX conversion
- XLS to XLSX conversion (Windows only, requires Excel)
- Folder monitoring with automatic conversion
- Multiple monitor profiles support
- Date detection (beta feature)
- Modern Fluent UI design
