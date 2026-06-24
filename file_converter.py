"""
File Converter with Folder Monitoring
Converts CSV and XLS files to XLSX format automatically.
"""

import csv
import math
import sys
import os
import time
import argparse
import subprocess
import re
import shutil
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr


try:
    import xlsxwriter

    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Regex for illegal XML characters
ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Excel limits and formula prefixes
EXCEL_MAX_CELL_CHARS = 32767
FORMULA_PREFIXES = ("=", "+", "-", "@")


# Date detection patterns
DATE_PATTERNS = [
    # DD/MM/YYYY or MM/DD/YYYY (ambiguous)
    (r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", "ambiguous"),
    # DD/MM/YY or MM/DD/YY (ambiguous, 2-digit year)
    (r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})$", "ambiguous_short"),
    # YYYY-MM-DD (ISO format, unambiguous)
    (r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", "iso"),
]


def detect_date_format_for_column(values):
    """
    Analyze a column's values to determine the most likely date format.
    Returns: 'dmy' (DD/MM/YYYY), 'mdy' (MM/DD/YYYY), 'iso' (YYYY-MM-DD), or None
    """
    dmy_score = 0  # DD/MM/YYYY evidence
    mdy_score = 0  # MM/DD/YYYY evidence
    iso_count = 0
    date_count = 0

    for val in values:
        if not isinstance(val, str):
            continue
        val = val.strip()
        if not val:
            continue

        # Check ISO format first (unambiguous)
        iso_match = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", val)
        if iso_match:
            iso_count += 1
            date_count += 1
            continue

        # Check ambiguous formats
        match = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", val)
        if match:
            first, second, _ = (
                int(match.group(1)),
                int(match.group(2)),
                match.group(3),
            )
            date_count += 1

            # If first > 12, it MUST be day (DD/MM/YYYY)
            if first > 12 and first <= 31:
                dmy_score += 10
            # If second > 12, it MUST be day (MM/DD/YYYY)
            elif second > 12 and second <= 31:
                mdy_score += 10
            # Both <= 12: ambiguous, give slight preference based on valid date check
            elif first <= 12 and second <= 12:
                # Could be either, no strong evidence
                pass

    # Need at least some date-like values
    if date_count < 1:
        return None

    # If mostly ISO format
    if iso_count > date_count * 0.5:
        return "iso"

    # Determine winner
    if dmy_score > mdy_score:
        return "dmy"
    elif mdy_score > dmy_score:
        return "mdy"
    elif date_count > 0:
        # Ambiguous - default to DMY (more common globally)
        return "dmy"

    return None


def parse_date_value(val, format_hint):
    """
    Parse a string value to a datetime object based on format hint.
    Returns (datetime_obj, excel_date_num) or (None, None) if not a date.
    """
    if not isinstance(val, str):
        return None, None

    val = val.strip()
    if not val:
        return None, None

    try:
        if format_hint == "iso":
            # YYYY-MM-DD or YYYY/MM/DD
            match = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", val)
            if match:
                year, month, day = (
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                )
                dt = datetime(year, month, day)
                return dt, None

        elif format_hint in ("dmy", "mdy"):
            match = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", val)
            if match:
                first, second, year_str = (
                    int(match.group(1)),
                    int(match.group(2)),
                    match.group(3),
                )
                year = int(year_str)

                # Handle 2-digit year
                if year < 100:
                    year = 2000 + year if year < 50 else 1900 + year

                if format_hint == "dmy":
                    day, month = first, second
                else:  # mdy
                    month, day = first, second

                # Validate
                if 1 <= month <= 12 and 1 <= day <= 31:
                    try:
                        dt = datetime(year, month, day)
                        return dt, None
                    except ValueError:
                        pass
    except Exception:
        pass

    return None, None


def analyze_columns_for_dates(data):
    """
    Analyze all columns to detect which ones contain dates and their format.
    Returns dict: {col_index: format_hint}
    """
    if not data:
        return {}

    num_cols = max(len(row) for row in data) if data else 0
    date_columns = {}

    for col_idx in range(num_cols):
        col_values = [row[col_idx] if col_idx < len(row) else "" for row in data]
        format_hint = detect_date_format_for_column(col_values)
        if format_hint:
            date_columns[col_idx] = format_hint

    return date_columns


def sanitize_for_xml(value):
    """Remove illegal XML characters from string values."""
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub("", value)
    return value


def sanitize_for_xlsx_cell(value):
    """Sanitize cell values for safe XLSX output."""
    value = sanitize_for_xml(value)
    if isinstance(value, str):
        if value.startswith(FORMULA_PREFIXES):
            value = "'" + value
        if len(value) > EXCEL_MAX_CELL_CHARS:
            value = value[:EXCEL_MAX_CELL_CHARS]
    return value


def clean_numeric(s):
    """
    Attempt to convert string to float, handling various formats.
    Returns original string if conversion fails or if value has leading zeros.
    """
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return s

    # If it starts with a backtick, it's text, so don't clean it.
    if s.startswith("`"):
        return s

    # Preserve strings with leading zeros (e.g., "000001", "007")
    # These are likely IDs, codes, or formatted numbers that should stay as text
    if len(s) > 1 and s[0] == "0" and s[1].isdigit():
        return s

    numeric_candidates = (
        s,
        s.replace(",", "."),
        s.replace(".", "").replace(",", "."),
        s.replace(",", ""),
    )
    for candidate in numeric_candidates:
        try:
            number = float(candidate)
        except ValueError:
            continue
        if math.isfinite(number):
            return number
        return s
    return s


def write_xlsx_with_xlsxwriter(
    header, data, output_path, text_columns=None, date_columns=None
):
    """Write data to XLSX file using XlsxWriter library."""
    if not XLSXWRITER_AVAILABLE:
        print("\nError: XlsxWriter library not found. Cannot create XLSX file.")
        print("Please install it by running: pip install XlsxWriter")
        return False

    with xlsxwriter.Workbook(output_path) as workbook:
        worksheet = workbook.add_worksheet("Sheet1")
        text_format = workbook.add_format({"num_format": "@"})
        date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
        max_lengths = [len(str(h)) for h in header]

        if text_columns:
            for col_idx in text_columns:
                worksheet.set_column(col_idx, col_idx, None, text_format)

        for col_num, cell_data in enumerate(header):
            worksheet.write(0, col_num, sanitize_for_xlsx_cell(cell_data))

        for row_num, row_data in enumerate(data, 1):
            for col_num, cell_data in enumerate(row_data):
                # Remove backtick prefix before sanitizing.
                if isinstance(cell_data, str) and cell_data.startswith("`"):
                    cell_data = cell_data[1:]
                sanitized_cell = sanitize_for_xlsx_cell(cell_data)

                # Check if this is a date column
                if date_columns and col_num in date_columns:
                    format_hint = date_columns[col_num]
                    dt, _ = parse_date_value(sanitized_cell, format_hint)
                    if dt:
                        worksheet.write_datetime(row_num, col_num, dt, date_format)
                        cell_len = 10  # yyyy-mm-dd length
                    else:
                        worksheet.write(row_num, col_num, sanitized_cell)
                        cell_len = len(str(sanitized_cell))
                else:
                    worksheet.write(row_num, col_num, sanitized_cell)
                    cell_len = len(str(sanitized_cell))

                if col_num < len(max_lengths):
                    if cell_len > max_lengths[col_num]:
                        max_lengths[col_num] = cell_len
                else:
                    max_lengths.append(cell_len)

        for col_num, max_len in enumerate(max_lengths):
            if not text_columns or col_num not in text_columns:
                worksheet.set_column(col_num, col_num, max_len + 2)
            else:
                worksheet.set_column(col_num, col_num, max(max_len + 2, 15))

    return True


def robust_csv_reader(file_path, remove_backticks=False):
    """
    Read CSV file with automatic encoding and delimiter detection.
    Returns (header, data, text_columns).
    """
    data = []
    header = []
    text_columns = set()

    # Try reading with different encodings
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            content = f.read()

    # Try to sniff the delimiter
    try:
        dialect = csv.Sniffer().sniff(content[:2048])
        delimiter = dialect.delimiter
    except csv.Error:
        # If sniffing fails, try common delimiters
        delimiters = [";", ",", "\t", "|"]
        best_delimiter = ","
        max_cols = 0
        for d in delimiters:
            lines = content.splitlines()
            cols = [len(line.split(d)) for line in lines]
            avg_cols = sum(cols) / len(cols) if cols else 0
            if avg_cols > max_cols:
                max_cols = avg_cols
                best_delimiter = d
        delimiter = best_delimiter if max_cols > 1 else ","

    lines = content.splitlines()
    reader = csv.reader(lines, delimiter=delimiter)
    all_rows = [row for row in reader if row]

    if not all_rows:
        return [], [], []

    # Determine maximum columns
    max_columns = max(len(row) for row in all_rows) if all_rows else 0
    if max_columns == 0:
        return [], [], []

    # First row is header, pad if needed
    header = all_rows[0]
    while len(header) < max_columns:
        header.append("")

    # Process data rows
    for row in all_rows[1:]:
        for i, cell in enumerate(row):
            if remove_backticks and isinstance(cell, str) and cell.startswith("`"):
                text_columns.add(i)

        cleaned_row = [clean_numeric(cell) for cell in row]
        while len(cleaned_row) < max_columns:
            cleaned_row.append("")
        data.append(cleaned_row)

    return header, data, list(text_columns)


def create_vbs_script():
    """Create VBScript content for XLS to XLSX conversion."""
    return """
Set objExcel = CreateObject("Excel.Application")
objExcel.Visible = False
objExcel.DisplayAlerts = False
On Error Resume Next
strXLSFile = WScript.Arguments(0)
strXLSXFile = WScript.Arguments(1)
Set objWorkbook = objExcel.Workbooks.Open(strXLSFile)
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to open XLS file: " & Err.Description
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.SaveAs strXLSXFile, 51
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to save as XLSX: " & Err.Description
    objWorkbook.Close False
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.Close False
objExcel.Quit
WScript.Quit(0)
"""


def convert_xls_to_xlsx(source_path, output_path):
    """Convert XLS file to XLSX using VBScript (Windows only)."""
    if sys.platform != "win32":
        print("Error: XLS conversion requires Windows with Microsoft Excel installed.")
        return False

    vbs_script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_temp_convert.vbs"
    )

    try:
        with open(vbs_script_path, "w", encoding="utf-8") as f:
            f.write(create_vbs_script())

        abs_vbs_path = os.path.abspath(vbs_script_path)
        abs_xls_path = os.path.abspath(source_path)
        abs_xlsx_path = os.path.abspath(output_path)

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        subprocess.run(
            ["cscript", "//Nologo", abs_vbs_path, abs_xls_path, abs_xlsx_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=creation_flags,
        )
        return True
    except FileNotFoundError:
        print("Error: 'cscript' not found. Windows Script Host is required.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error converting XLS: {e.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        print("Error: Conversion timed out.")
        return False
    finally:
        if os.path.exists(vbs_script_path):
            os.remove(vbs_script_path)


def convert_to_xlsx(
    source_path, output_path=None, remove_backticks=False, auto_detect_dates=False
):
    """
    Convert CSV or XLS file to XLSX format.

    Args:
        source_path: Path to source file (CSV or XLS)
        output_path: Optional output path. If None, uses source name with .xlsx extension
        remove_backticks: If True, remove backtick prefixes and mark columns as text
        auto_detect_dates: If True, detect and convert date columns (BETA)

    Returns:
        Output path on success, None on failure
    """
    source_path = os.path.abspath(source_path)
    _, file_extension = os.path.splitext(source_path)
    file_extension = file_extension.lower()

    if output_path is None:
        output_path = os.path.splitext(source_path)[0] + ".xlsx"

    if file_extension == ".xlsx":
        # Already XLSX, just copy if different path
        if os.path.abspath(output_path) != source_path:
            shutil.copy(source_path, output_path)
        return output_path

    elif file_extension == ".xls":
        if convert_xls_to_xlsx(source_path, output_path):
            return output_path
        return None

    elif file_extension == ".csv":
        header, data, text_columns = robust_csv_reader(
            source_path, remove_backticks=remove_backticks
        )
        if not header and not data:
            print(f"Error: Failed to read CSV file: {source_path}")
            return None

        # Auto-detect date columns if enabled
        date_columns = None
        if auto_detect_dates:
            date_columns = analyze_columns_for_dates(data)

        if write_xlsx_with_xlsxwriter(
            header, data, output_path, text_columns, date_columns
        ):
            return output_path
        return None

    else:
        print(f"Error: Unsupported file format '{file_extension}'. Use CSV or XLS.")
        return None
        return None


# =============================================================================
# Folder Monitoring
# =============================================================================


class ConversionHandler(FileSystemEventHandler):
    """Handle file system events for automatic conversion."""

    def __init__(self, output_folder=None, delete_source=False, exclude_keywords=""):
        super().__init__()
        self.output_folder = output_folder
        self.delete_source = delete_source
        self.exclude_keywords = exclude_keywords
        self.processing = set()  # Track files being processed to avoid duplicates

    def _matches_exclude_keyword(self, file_path: str) -> bool:
        """Check if filename contains any exclude keyword."""
        if not self.exclude_keywords:
            return False

        filename = os.path.basename(file_path).lower()
        keywords = [
            k.strip().lower() for k in self.exclude_keywords.split(",") if k.strip()
        ]

        for keyword in keywords:
            if keyword in filename:
                return True
        return False

    def _should_process(self, file_path):
        """Check if file should be processed."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".csv", ".xls"]:
            return False
        if self._matches_exclude_keyword(file_path):
            return False
        return True

    def _get_output_path(self, source_path):
        """Generate output path for converted file."""
        base_name = os.path.splitext(os.path.basename(source_path))[0] + ".xlsx"
        if self.output_folder:
            return os.path.join(self.output_folder, base_name)
        return os.path.join(os.path.dirname(source_path), base_name)

    def _process_file(self, file_path):
        """Process a single file for conversion."""
        if file_path in self.processing:
            return

        if not self._should_process(file_path):
            return

        # Wait a bit to ensure file is fully written
        time.sleep(0.5)

        if not os.path.exists(file_path):
            return

        self.processing.add(file_path)

        try:
            output_path = self._get_output_path(file_path)
            print(
                f"\n[Converting] {os.path.basename(file_path)} -> {os.path.basename(output_path)}"
            )

            result = convert_to_xlsx(file_path, output_path)

            if result:
                print(f"[Success] Created: {output_path}")
                if self.delete_source:
                    os.remove(file_path)
                    print(f"[Deleted] Source file removed: {file_path}")
            else:
                print(f"[Failed] Could not convert: {file_path}")

        except Exception as e:
            print(f"[Error] {file_path}: {e}")

        finally:
            self.processing.discard(file_path)

    def on_created(self, event):
        """Handle file creation events."""
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            self._process_file(event.src_path)

    def on_moved(self, event):
        """Handle file move events (file moved into watched folder)."""
        if isinstance(event, FileMovedEvent) and not event.is_directory:
            self._process_file(event.dest_path)


def process_existing_files(
    folder_path, output_folder=None, delete_source=False, exclude_keywords=""
):
    """Process any existing CSV/XLS files in the folder."""
    folder = Path(folder_path)
    files_to_process = list(folder.glob("*.csv")) + list(folder.glob("*.xls"))

    # Filter out excluded files
    if exclude_keywords:
        keywords = [k.strip().lower() for k in exclude_keywords.split(",") if k.strip()]
        files_to_process = [
            f
            for f in files_to_process
            if not any(kw in f.name.lower() for kw in keywords)
        ]

    if not files_to_process:
        print("No existing CSV/XLS files found (or all excluded).")
        return

    print(f"Found {len(files_to_process)} existing file(s) to convert...")

    for file_path in files_to_process:
        file_path_str = str(file_path)
        base_name = os.path.splitext(file_path.name)[0] + ".xlsx"

        if output_folder:
            output_path = os.path.join(output_folder, base_name)
        else:
            output_path = os.path.join(folder_path, base_name)

        print(f"\n[Converting] {file_path.name}")
        result = convert_to_xlsx(file_path_str, output_path)

        if result:
            print(f"[Success] Created: {output_path}")
            if delete_source:
                os.remove(file_path_str)
                print("[Deleted] Source removed")
        else:
            print("[Failed] Could not convert")


def monitor_folder(
    folder_path,
    output_folder=None,
    delete_source=False,
    process_existing=True,
    exclude_keywords="",
):
    """
    Monitor a folder for new CSV/XLS files and convert them to XLSX.

    Args:
        folder_path: Path to folder to monitor
        output_folder: Optional separate folder for output files
        delete_source: If True, delete source files after successful conversion
        process_existing: If True, process existing files before starting monitor
        exclude_keywords: Comma-separated keywords to exclude files by name
    """
    if not WATCHDOG_AVAILABLE:
        print("Error: watchdog library not found.")
        print("Please install it by running: pip install watchdog")
        return

    if not os.path.isdir(folder_path):
        print(f"Error: Folder not found: {folder_path}")
        return

    if output_folder and not os.path.isdir(output_folder):
        os.makedirs(output_folder, exist_ok=True)
        print(f"Created output folder: {output_folder}")

    # Process existing files first
    if process_existing:
        process_existing_files(
            folder_path, output_folder, delete_source, exclude_keywords
        )

    # Set up monitoring
    event_handler = ConversionHandler(output_folder, delete_source, exclude_keywords)
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=False)
    observer.start()

    print(f"\n{'=' * 60}")
    print(f"Monitoring folder: {folder_path}")
    if output_folder:
        print(f"Output folder: {output_folder}")
    print(f"Delete source after conversion: {delete_source}")
    if exclude_keywords:
        print(f"Exclude keywords: {exclude_keywords}")
    print(f"{'=' * 60}")
    print("Press Ctrl+C to stop monitoring...\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        observer.stop()

    observer.join()
    print("Monitor stopped.")


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV/XLS files to XLSX format with optional folder monitoring.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a single file
  python file_converter.py input.csv
  python file_converter.py data.xls -o output.xlsx
  
  # Monitor a folder for new files
  python file_converter.py --monitor /path/to/folder
  python file_converter.py --monitor ./inbox --output ./converted --delete-source
        """,
    )

    parser.add_argument("input", nargs="?", help="Input file path (CSV or XLS)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (for single file) or folder (for monitor mode)",
    )
    parser.add_argument(
        "--monitor", metavar="FOLDER", help="Monitor folder for new CSV/XLS files"
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete source files after successful conversion",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="In monitor mode, skip processing existing files",
    )
    parser.add_argument(
        "--remove-backticks",
        action="store_true",
        help="Remove backtick prefixes from text columns",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Silent mode: no console output, show Windows notification on completion",
    )
    parser.add_argument(
        "--exclude",
        metavar="KEYWORDS",
        help="Comma-separated keywords to exclude (files with these in name are skipped)",
    )

    args = parser.parse_args()

    # Monitor mode
    if args.monitor:
        monitor_folder(
            args.monitor,
            output_folder=args.output,
            delete_source=args.delete_source,
            process_existing=not args.skip_existing,
            exclude_keywords=args.exclude or "",
        )
        return

    # Single file mode
    if args.input:
        if not os.path.exists(args.input):
            if not args.silent:
                print(f"Error: File not found: {args.input}")
            sys.exit(1)

        if args.silent:
            with open(os.devnull, "w") as devnull:
                with redirect_stdout(devnull), redirect_stderr(devnull):
                    result = convert_to_xlsx(
                        args.input, args.output, args.remove_backticks
                    )
        else:
            result = convert_to_xlsx(args.input, args.output, args.remove_backticks)

        if result:
            # Add to recent conversions history
            try:
                from history_util import add_to_history

                add_to_history(
                    source_path=os.path.abspath(args.input),
                    output_path=os.path.abspath(result),
                    status="success",
                )
            except ImportError:
                pass  # History utility not available

            if args.silent:
                # Show Windows toast notification
                try:
                    from context_menu import show_windows_notification

                    filename = os.path.basename(result)
                    show_windows_notification(
                        "Conversion Complete",
                        f"Successfully converted to {filename}",
                        "info",
                    )
                except ImportError:
                    pass  # Silent mode, no output
            else:
                print(f"Successfully converted to: {result}")
        else:
            # Add to recent conversions history as failed
            try:
                from history_util import add_to_history

                output_path = args.output or os.path.splitext(args.input)[0] + ".xlsx"
                add_to_history(
                    source_path=os.path.abspath(args.input),
                    output_path=os.path.abspath(output_path),
                    status="failed",
                    error_message="Conversion failed",
                )
            except ImportError:
                pass  # History utility not available

            if args.silent:
                try:
                    from context_menu import show_windows_notification

                    filename = os.path.basename(args.input)
                    show_windows_notification(
                        "Conversion Failed", f"Failed to convert {filename}", "error"
                    )
                except ImportError:
                    pass
            else:
                print("Conversion failed.")
            sys.exit(1)
        return

    # No arguments provided
    parser.print_help()


if __name__ == "__main__":
    main()
