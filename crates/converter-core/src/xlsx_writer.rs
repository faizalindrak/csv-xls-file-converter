use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use rust_xlsxwriter::{Format, Workbook, XlsxError};

use crate::{
    detect_date_format_for_column, parse_date_value, sanitize_for_xlsx_cell, CellValue,
    ConvertError, CsvTable, DateFormat,
};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ConvertOptions {
    pub remove_backticks: bool,
    pub auto_detect_dates: bool,
}

pub fn write_xlsx(
    table: &CsvTable,
    output_path: &Path,
    auto_detect_dates: bool,
) -> Result<(), ConvertError> {
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();
    worksheet.set_name("Sheet1").map_err(map_xlsx_error)?;

    let text_format = Format::new().set_num_format("@");
    let date_format = Format::new().set_num_format("yyyy-mm-dd");
    let date_columns = if auto_detect_dates {
        analyze_date_columns(table)
    } else {
        BTreeMap::new()
    };
    let mut max_lengths: Vec<usize> = table.header.iter().map(String::len).collect();

    for (col, header) in table.header.iter().enumerate() {
        worksheet
            .write_string(0, col as u16, sanitize_for_xlsx_cell(header))
            .map_err(map_xlsx_error)?;
    }

    for (row_index, row) in table.rows.iter().enumerate() {
        let excel_row = (row_index + 1) as u32;
        for (col, cell) in row.cells.iter().enumerate() {
            let text = sanitize_for_xlsx_cell(&cell.raw);
            if let Some(format) = date_columns.get(&col) {
                if let Some(date) = parse_date_value(&text, *format) {
                    worksheet
                        .write_datetime_with_format(excel_row, col as u16, date, &date_format)
                        .map_err(map_xlsx_error)?;
                    max_lengths[col] = max_lengths[col].max(10);
                    continue;
                }
            }
            match &cell.value {
                CellValue::Number(number) => worksheet
                    .write_number(excel_row, col as u16, *number)
                    .map_err(map_xlsx_error)?,
                CellValue::Text(_) => worksheet
                    .write_string(excel_row, col as u16, &text)
                    .map_err(map_xlsx_error)?,
            };
            max_lengths[col] = max_lengths[col].max(text.len());
        }
    }

    for (col, width) in max_lengths.iter().enumerate() {
        if table.text_columns.contains(&col) {
            worksheet
                .set_column_format(col as u16, &text_format)
                .map_err(map_xlsx_error)?;
            worksheet
                .set_column_width(col as u16, (*width + 2).max(15) as f64)
                .map_err(map_xlsx_error)?;
        } else {
            worksheet
                .set_column_width(col as u16, (*width + 2) as f64)
                .map_err(map_xlsx_error)?;
        }
    }

    workbook.save(output_path).map_err(map_xlsx_error)
}

pub fn convert_csv_to_xlsx(
    input: &Path,
    output: &Path,
    options: ConvertOptions,
) -> Result<PathBuf, ConvertError> {
    let table = crate::read_csv(input, options.remove_backticks)?;
    write_xlsx(&table, output, options.auto_detect_dates)?;
    Ok(output.to_path_buf())
}

fn analyze_date_columns(table: &CsvTable) -> BTreeMap<usize, DateFormat> {
    let mut columns = BTreeMap::new();
    let column_count = table.header.len();
    for col in 0..column_count {
        let values: Vec<&str> = table
            .rows
            .iter()
            .map(|row| {
                row.cells
                    .get(col)
                    .map(|cell| cell.raw.as_str())
                    .unwrap_or("")
            })
            .collect();
        if let Some(format) = detect_date_format_for_column(&values) {
            columns.insert(col, format);
        }
    }
    columns
}

fn map_xlsx_error(source: XlsxError) -> ConvertError {
    ConvertError::XlsxWrite(source.to_string())
}
