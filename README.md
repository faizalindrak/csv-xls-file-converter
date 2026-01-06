# CSV/XLS to XLSX Converter

A robust tool to convert CSV and XLS files to XLSX format. It features a modern GUI, a command-line interface, and an automated folder monitoring system.

## Features

- **Convert CSV to XLSX**: Handles various delimiters and encodings automatically.
- **Convert XLS to XLSX**: Uses Windows Script Host (requires Excel) to convert legacy XLS files.
- **Folder Monitoring**: Watch a folder for new files and automatically convert them.
- **Date Detection (Beta)**: Intelligent auto-detection of date formats (DD/MM/YYYY vs MM/DD/YYYY).
- **Modern GUI**: Built with PySide6 and PyQt-Fluent-Widgets for a native Windows 11 look and feel.
- **CLI Support**: Full command-line interface for automation and scripting.
- **Optimization**: Batch processing for handling large numbers of files efficiently.

## Requirements

- Python 3.8+
- Microsoft Excel (required for XLS to XLSX conversion on Windows)
- Windows (recommended for full feature support, though CSV conversion works cross-platform)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/faizalindrak/csv-xls-file-converter.git
   cd csv-xls-file-converter
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### GUI Mode

Run the graphical interface:
```bash
python gui.py
```
- **Convert File**: Select a single file to convert immediately.
- **Monitor Folder**: Choose a folder to watch. Any CSV/XLS file dropped there will be converted automatically.

### Command Line Interface (CLI)

The `file_converter.py` script provides a powerful CLI.

**Convert a single file:**
```bash
python file_converter.py input.csv
python file_converter.py input.xls -o output.xlsx
```

**Monitor a folder:**
```bash
# Basic monitoring
python file_converter.py --monitor "C:\path\to\folder"

# Monitor and output to a specific directory
python file_converter.py --monitor "C:\input" --output "C:\output"

# Delete source files after conversion
python file_converter.py --monitor "C:\input" --delete-source
```

**Options:**
- `--monitor FOLDER`: Watch a folder for new files.
- `-o, --output PATH`: Specify output file or folder.
- `--delete-source`: Delete original files after successful conversion.
- `--skip-existing`: Don't process files already present in the folder (monitor mode only).
- `--remove-backticks`: Remove leading backticks from text columns.

## Notes

- **XLS Conversion**: Requires Microsoft Excel installed on the machine as it uses VBScript automation. This feature is Windows-only.
- **Date Detection**: The date detection is in Beta. It attempts to distinguish between DMY and MDY formats based on column analysis.

## License

[MIT License](LICENSE)
