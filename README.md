# CSV/XLS to XLSX Converter

A Windows-focused converter for CSV and legacy XLS files, with a Slint GUI, a Rust CLI, and folder monitoring for automated conversion workflows.

## Features

- **CSV to XLSX**: Handles encodings, delimiter parsing, text preservation, formula escaping, and Excel-safe XML sanitization.
- **XLS to XLSX**: Uses Windows Script Host and Microsoft Excel automation for legacy XLS files.
- **Folder Monitoring**: Watches a folder for new CSV/XLS files and converts them automatically.
- **Date Detection (Beta)**: Detects common DMY and MDY date columns during CSV conversion.
- **Slint GUI**: Native Rust desktop interface for single-file conversion, profiles, history, and settings.
- **CLI Support**: Automation-friendly command-line interface for one-off conversion and monitoring.

## Requirements

- Rust stable toolchain for source builds: https://rustup.rs
- Microsoft Excel on Windows for XLS to XLSX conversion
- Windows for full feature support; CSV conversion builds cross-platform
- Inno Setup 6.x only when building the Windows installer

## Development Setup

```bash
git clone https://github.com/faizalindrak/csv-xls-file-converter.git
cd csv-xls-file-converter
cargo test --workspace
```

## Usage

### GUI

Run the Slint GUI from source:

```bash
cargo run -p converter-gui
```

Build and run the release GUI:

```bash
cargo build --release -p converter-gui
target\release\csv-xls-converter-gui.exe
```

### CLI

Convert a single file:

```bash
cargo run -p converter-cli -- input.csv
cargo run -p converter-cli -- input.xls --output output.xlsx
```

Monitor a folder:

```bash
cargo run -p converter-cli -- --monitor "C:\path\to\folder"
cargo run -p converter-cli -- --monitor "C:\input" --output "C:\output"
cargo run -p converter-cli -- --monitor "C:\input" --delete-source
cargo run -p converter-cli -- --monitor "C:\input" --exclude "temp,backup,draft"
```

CLI options:

- `--monitor FOLDER`: Watch a folder for new files.
- `-o, --output PATH`: Specify output file or folder.
- `--delete-source`: Delete original files after successful conversion.
- `--skip-existing`: Do not process files already present in the folder.
- `--remove-backticks`: Remove leading backticks from text columns.
- `--silent`: Suppress console output and use Windows notification hooks when available.
- `--exclude KEYWORDS`: Comma-separated keywords; matching filenames are skipped in monitor mode.

## Building Releases

Build the portable GUI and CLI executables:

```bat
build.bat
```

Build the executables and Windows installer:

```bat
build.bat full
```

Build outputs:

- `dist\CSV-XLS-Converter.exe`: Slint GUI executable, also used for Explorer `--silent` context-menu conversion.
- `dist\CSV-XLS-Converter-CLI.exe`: Command-line executable for automation.
- `dist\CSV-XLS-Converter-Setup-{version}.exe`: Windows installer, created by `build.bat full`.

## Notes

- XLS conversion is Windows-only and requires Microsoft Excel because it uses VBScript automation through `cscript`.
- Settings remain compatible with `%APPDATA%\csv-xls-converter\profiles.json` from the Python app.
- The Python implementation files are retained for reference during the port, but release builds now use the Rust workspace.

## License

[MIT License](LICENSE)
