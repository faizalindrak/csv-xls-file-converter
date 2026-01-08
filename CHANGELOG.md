# Changelog

All notable changes to this project will be documented in this file.

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
