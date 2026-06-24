use std::fs;
use std::path::Path;

use encoding_rs::WINDOWS_1252;

use crate::{clean_numeric, CellValue, ConvertError};

#[derive(Clone, Debug, PartialEq)]
pub struct CsvCell {
    pub raw: String,
    pub value: CellValue,
}

#[derive(Clone, Debug, PartialEq)]
pub struct CsvRow {
    pub cells: Vec<CsvCell>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct CsvTable {
    pub header: Vec<String>,
    pub rows: Vec<CsvRow>,
    pub text_columns: Vec<usize>,
}

pub fn read_csv(path: &Path, remove_backticks: bool) -> Result<CsvTable, ConvertError> {
    let bytes = fs::read(path).map_err(|source| ConvertError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let content = match String::from_utf8(bytes.clone()) {
        Ok(text) => text,
        Err(_) => {
            let (decoded, _, _) = WINDOWS_1252.decode(&bytes);
            decoded.into_owned()
        }
    };
    let delimiter = sniff_delimiter(&content);
    let mut reader = csv::ReaderBuilder::new()
        .has_headers(false)
        .flexible(true)
        .delimiter(delimiter)
        .from_reader(content.as_bytes());

    let mut rows: Vec<Vec<String>> = Vec::new();
    for record in reader.records() {
        let record = record.map_err(|err| ConvertError::CsvRead(err.to_string()))?;
        let row: Vec<String> = record.iter().map(ToOwned::to_owned).collect();
        if !row.is_empty() {
            rows.push(row);
        }
    }

    if rows.is_empty() {
        return Err(ConvertError::CsvRead(path.display().to_string()));
    }

    let max_columns = rows.iter().map(Vec::len).max().unwrap_or(0);
    let mut header = rows.remove(0);
    header.resize(max_columns, String::new());

    let mut text_columns = Vec::new();
    let mut data_rows = Vec::new();
    for row in rows {
        let mut cells = Vec::new();
        for index in 0..max_columns {
            let mut raw = row.get(index).cloned().unwrap_or_default();
            if remove_backticks && raw.starts_with('`') {
                if !text_columns.contains(&index) {
                    text_columns.push(index);
                }
                raw.remove(0);
            }
            let value = clean_numeric(&raw);
            cells.push(CsvCell { raw, value });
        }
        data_rows.push(CsvRow { cells });
    }

    Ok(CsvTable {
        header,
        rows: data_rows,
        text_columns,
    })
}

fn sniff_delimiter(content: &str) -> u8 {
    let sample = content.lines().take(10).collect::<Vec<_>>();
    let candidates = [b';', b',', b'\t', b'|'];
    candidates
        .into_iter()
        .max_by_key(|candidate| {
            sample
                .iter()
                .map(|line| {
                    line.as_bytes()
                        .iter()
                        .filter(|byte| *byte == candidate)
                        .count()
                })
                .sum::<usize>()
        })
        .filter(|candidate| {
            sample
                .iter()
                .any(|line| line.as_bytes().contains(candidate))
        })
        .unwrap_or(b',')
}
