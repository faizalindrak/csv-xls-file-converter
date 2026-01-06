import csv
import sys
import os
import argparse
from collections import defaultdict
import subprocess

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False

import re

ILLEGAL_CHARACTERS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def sanitize_for_xml(value):
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub('', value)
    return value

def detect_and_standardize_decimal(value):
    if isinstance(value, str):
        return value.replace(',', '.')
    return value

def write_xlsx_with_xlsxwriter(header, data, output_path, text_columns=None):
    if not XLSXWRITER_AVAILABLE:
        print("\nError: XlsxWriter library not found. Cannot create XLSX file.")
        print("Please install it by running: pip install XlsxWriter")
        return

    with xlsxwriter.Workbook(output_path) as workbook:
        worksheet = workbook.add_worksheet("Sheet1")
        text_format = workbook.add_format({'num_format': '@'})
        max_lengths = [len(str(h)) for h in header]

        if text_columns:
            for col_idx in text_columns:
                # Set the format for the entire column
                worksheet.set_column(col_idx, col_idx, None, text_format)

        for col_num, cell_data in enumerate(header):
            worksheet.write(0, col_num, sanitize_for_xml(cell_data))

        for row_num, row_data in enumerate(data, 1):
            for col_num, cell_data in enumerate(row_data):
                sanitized_cell = sanitize_for_xml(cell_data)
                # Backtick is removed here, before writing
                if isinstance(sanitized_cell, str) and sanitized_cell.startswith('`'):
                    sanitized_cell = sanitized_cell[1:]
                
                # The column is already formatted, so we just write the value
                worksheet.write(row_num, col_num, sanitized_cell)

                if col_num < len(max_lengths):
                    if len(str(sanitized_cell)) > max_lengths[col_num]:
                        max_lengths[col_num] = len(str(sanitized_cell))
                else:
                    max_lengths.append(len(str(sanitized_cell)))

        for col_num, max_len in enumerate(max_lengths):
            # Adjust column width, but don't override the format
            if not text_columns or col_num not in text_columns:
                 worksheet.set_column(col_num, col_num, max_len + 2)
            else: # For text columns, we might want a bit more space
                 worksheet.set_column(col_num, col_num, max(max_len + 2, 15))


def find_and_read_data(file_path):
    if not PANDAS_AVAILABLE:
        print("\nError: pandas library is required for this script.")
        print("Please install it by running: pip install pandas openpyxl")
        return None, None

    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"The file '{file_path}' does not exist.")
        _, file_extension = os.path.splitext(file_path)
        df = None

        if file_extension.lower() == '.csv':
            try:
                # Try common encodings
                df = pd.read_csv(file_path, sep=None, engine='python', dtype=str, encoding='utf-8').fillna('')
            except (UnicodeDecodeError, csv.Error):
                try:
                    df = pd.read_csv(file_path, sep=None, engine='python', dtype=str, encoding='latin-1').fillna('')
                except Exception as e:
                    print(f"Error reading CSV with multiple encodings: {e}")
                    return None, None
            except Exception as e:
                print(f"Error reading file: {e}")
                return None, None

        elif file_extension.lower() in ['.xlsx', '.xls']:
            try:
                df = pd.read_excel(file_path, dtype=str).fillna('')
            except Exception as e:
                print(f"Error reading Excel file: {e}")
                return None, None
        else:
            print(f"Error: Unsupported file format '{file_extension}'. Please use CSV or XLSX.")
            return None, None

        if df is None:
            return None, None

        # The BoM conversion logic will now need to find its own header.
        # This function is now generic.
        return df.columns.tolist(), df.values.tolist()
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None, None

def clean_numeric(s):
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return s
    
    # If it starts with a backtick, it's text, so don't clean it.
    if s.startswith('`'):
        return s

    # Try to convert to float directly
    try:
        return float(s)
    except ValueError:
        pass

    # Try replacing comma with dot (for cases like "1,23")
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        pass

    # Try removing dots (as thousand separators) and replacing comma with dot (as decimal)
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except ValueError:
        pass

    # Try removing commas (as thousand separators)
    try:
        return float(s.replace(',', ''))
    except ValueError:
        pass

    return s # Return original string if all parsing fails

def robust_csv_reader(file_path, remove_backticks=False):
    data = []
    header = []
    text_columns = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()

    # Try to sniff the delimiter
    try:
        dialect = csv.Sniffer().sniff(content[:2048])
        delimiter = dialect.delimiter
    except csv.Error:
        # If sniffing fails, try common delimiters
        delimiters = [';', ',', '	', '|']
        best_delimiter = ''
        max_cols = 0
        for d in delimiters:
            lines = content.splitlines()
            cols = [len(line.split(d)) for line in lines]
            avg_cols = sum(cols) / len(cols) if cols else 0
            if avg_cols > max_cols:
                max_cols = avg_cols
                best_delimiter = d
        delimiter = best_delimiter if max_cols > 1 else ','

    lines = content.splitlines()
    reader = csv.reader(lines, delimiter=delimiter)
    all_rows = [row for row in reader if row] # Filter out empty rows

    if not all_rows:
        return [], [], []

    # Determine the maximum number of columns in the entire file
    max_columns = 0
    for row in all_rows:
        if len(row) > max_columns:
            max_columns = len(row)
            
    if max_columns == 0:
        return [], [], []

    # Assume the first row is the header, and pad it if it's shorter than max_columns
    header = all_rows[0]
    while len(header) < max_columns:
        header.append('')

    data = []
    # Start from the second row for data
    for row in all_rows[1:]:
        # We don't remove the backtick here, just identify the columns
        for i, cell in enumerate(row):
            if remove_backticks and isinstance(cell, str) and cell.startswith('`'):
                text_columns.add(i)
        
        cleaned_row = [clean_numeric(cell) for cell in row]
        # Pad rows that are shorter than the max number of columns
        while len(cleaned_row) < max_columns:
            cleaned_row.append('')
        data.append(cleaned_row)

    return header, data, list(text_columns)

def convert_to_xlsx(source_path, output_path, remove_backticks=False):
    _, file_extension = os.path.splitext(source_path)
    
    if file_extension.lower() == '.xls':
        # Logic to convert .xls to .xlsx using VBScript
        vbs_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_xls_to_xlsx_temp.vbs")
        vbs_script_content = '''
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
objWorkbook.SaveAs strXLSXFile, 51 ' 51 = xlOpenXMLWorkbook
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to save as XLSX: " & Err.Description
    objWorkbook.Close False
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.Close False
objExcel.Quit
WScript.Quit(0)
'''
        try:
            with open(vbs_script_path, "w", encoding="utf-8") as f:
                f.write(vbs_script_content)
            
            abs_vbs_path = os.path.abspath(vbs_script_path)
            abs_xls_path = os.path.abspath(source_path)
            abs_xlsx_path = os.path.abspath(output_path)

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            subprocess.run(
                ["cscript", "//Nologo", abs_vbs_path, abs_xls_path, abs_xlsx_path],
                check=True, capture_output=True, text=True, timeout=120,
                creationflags=creation_flags
            )
            return output_path
        finally:
            if os.path.exists(vbs_script_path):
                os.remove(vbs_script_path)

    elif file_extension.lower() == '.csv':
        header, data, text_columns = robust_csv_reader(source_path, remove_backticks=remove_backticks)
        if not header and not data:
            raise ValueError("Failed to read or parse the CSV file.")
        write_xlsx_with_xlsxwriter(header, data, output_path, text_columns)
        return output_path

    elif file_extension.lower() == '.xlsx':
        # If it's already an xlsx, just copy it
        import shutil
        shutil.copy(source_path, output_path)
        return output_path

    else:
        raise ValueError("Unsupported file format for conversion to XLSX.")

def convert_to_multi_level_bom(sl_bom_path, output_path, output_format):
    file_to_process = sl_bom_path
    temp_xlsx_path = None
    vbs_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_xls_to_xlsx_temp.vbs")

    if sl_bom_path.lower().endswith('.xls'):
        print("Detected .xls file. Attempting conversion to .xlsx via VBScript...")
        vbs_script_content = '''
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
objWorkbook.SaveAs strXLSXFile, 51 ' 51 = xlOpenXMLWorkbook
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to save as XLSX: " & Err.Description
    objWorkbook.Close False
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.Close False
objExcel.Quit
WScript.Quit(0)
'''
        try:
            with open(vbs_script_path, "w", encoding="utf-8") as f:
                f.write(vbs_script_content)
            
            temp_xlsx_path = os.path.splitext(sl_bom_path)[0] + "_temp.xlsx"
            
            abs_vbs_path = os.path.abspath(vbs_script_path)
            abs_xls_path = os.path.abspath(sl_bom_path)
            abs_xlsx_path = os.path.abspath(temp_xlsx_path)

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            subprocess.run(
                ["cscript", "//Nologo", abs_vbs_path, abs_xls_path, abs_xlsx_path],
                check=True, capture_output=True, text=True, timeout=120,
                creationflags=creation_flags
            )
            print(f"Successfully converted to temporary file: {os.path.basename(temp_xlsx_path)}")
            file_to_process = temp_xlsx_path
        except FileNotFoundError:
            print("\nError: 'cscript' not found. This feature requires Windows Script Host.")
            return
        except subprocess.CalledProcessError as e:
            print(f"\nError converting .xls to .xlsx. Please ensure Microsoft Excel is installed.")
            print(f"Details: {e.stderr.strip()}")
            return
        except Exception as e:
            print(f"\nAn unexpected error occurred during conversion: {e}")
            return
        finally:
            if os.path.exists(vbs_script_path):
                os.remove(vbs_script_path)
    
    try:
        print("Reading and processing BOM data...")
        header, data = find_and_read_data(file_to_process)
        if header is None:
            print("Error: Could not read the file.")
            return

        # Find the header row containing 'SKU (SFG/FG)' dynamically
        header_row_index = -1
        for i, row in enumerate(data[:20]):
            if any('SKU (SFG/FG)' in str(cell) for cell in row):
                header_row_index = i
                break
        
        if header_row_index == -1:
            print("Error: Could not find the header row containing 'SKU (SFG/FG)'.")
            return

        # Adjust data and header based on the found header row
        header = data[header_row_index]
        data = data[header_row_index + 1:]

        sfg_to_children = defaultdict(list)
        sku_to_row_map = {}
        numeric_indices = [9, 10, 11]

        for row in data:
            if not row or len(row) < 12:
                continue
            for idx in numeric_indices:
                if idx < len(row):
                    try:
                        val = detect_and_standardize_decimal(row[idx])
                        row[idx] = float(val)
                    except (ValueError, TypeError):
                        row[idx] = 0.0
            parent_sku = str(row[0])
            sfg_to_children[parent_sku].append(row)
            if parent_sku not in sku_to_row_map:
                sku_to_row_map[parent_sku] = row

        all_parent_skus = list(sfg_to_children.keys())
        print(f"Found {len(all_parent_skus)} unique parent SKUs to process.")

        output_data = []
        new_header = header[:5] + ['Level'] + header[5:]

        pbar = None
        try:
            from tqdm import tqdm
            # In some environments (like a frozen GUI app), stderr might not be available.
            if sys.stderr:
                pbar = tqdm(total=len(all_parent_skus), desc="Converting BOM", unit="SKU")
        except ImportError:
            print("tqdm not found. Progress will not be shown. To see progress, run: pip install tqdm")

        def get_children_recursive(parent_sku, level, multiplier, top_level_parent_row, memo):
            if parent_sku not in sfg_to_children:
                return
            for child_row in sfg_to_children[parent_sku]:
                child_sku = str(child_row[5])
                memo_key = (top_level_parent_row[0], parent_sku, child_sku)
                if memo_key in memo:
                    continue
                memo.add(memo_key)
                base_quantity = child_row[9]
                cumulative_quantity = base_quantity * multiplier
                output_row = top_level_parent_row[:5] + [int(level)] + child_row[5:9] + [cumulative_quantity] + child_row[10:]
                output_data.append(output_row)
                if child_sku in sfg_to_children:
                    get_children_recursive(child_sku, level + 1, base_quantity, top_level_parent_row, memo)

        for parent_sku in all_parent_skus:
            top_level_parent_row = sku_to_row_map.get(parent_sku)
            if top_level_parent_row:
                memo = set()
                get_children_recursive(parent_sku, 1, 1.0, top_level_parent_row, memo)
            if pbar:
                pbar.update(1)

        if pbar:
            pbar.close()

        if output_format == 'csv':
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.writer(outfile, delimiter=';')
                writer.writerow(new_header)
                writer.writerows(output_data)
        elif output_format == 'xlsx':
            write_xlsx_with_xlsxwriter(new_header, output_data, output_path)

        print("\nConversion Finished!")
        print("--- Stats ---")
        print(f"Total lines read from input file: {len(data)}")
        print(f"Total parent SKUs processed: {len(all_parent_skus)}")
        print(f"Total lines written to output file: {len(output_data)}")

    finally:
        if temp_xlsx_path and os.path.exists(temp_xlsx_path):
            # As requested, the temporary .xlsx file is no longer deleted.
            print(f"Temporary file from .xls conversion has been kept: {temp_xlsx_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a single-level BOM to a multi-level BOM.")
    parser.add_argument("input_file", help="The path to the single-level BOM file (CSV or XLSX).")
    parser.add_argument("--format", choices=['csv', 'xlsx'], help="The output file format.")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at {args.input_file}")
        sys.exit(1)

    output_format = args.format
    if not output_format:
        while True:
            choice = input("Choose output format (csv/xlsx): ").lower()
            if choice in ['csv', 'xlsx']:
                output_format = choice
                break
            else:
                print("Invalid choice. Please enter 'csv' or 'xlsx'.")

    base, _ = os.path.splitext(args.input_file)
    output_file = f"{base} multi level.{output_format}"
    print(f"Output will be saved to: {output_file}")
    convert_to_multi_level_bom(args.input_file, output_file, output_format)
