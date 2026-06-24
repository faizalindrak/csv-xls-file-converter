mod csv_reader;
mod dates;
mod error;
mod numeric;
mod sanitize;
mod xlsx_writer;

use std::path::{Path, PathBuf};

pub use csv_reader::{read_csv, CsvCell, CsvRow, CsvTable};
pub use dates::{detect_date_format_for_column, parse_date_value, DateFormat};
pub use error::ConvertError;
pub use numeric::{clean_numeric, CellValue};
pub use sanitize::{sanitize_for_xlsx_cell, sanitize_for_xml, EXCEL_MAX_CELL_CHARS};
pub use xlsx_writer::{convert_csv_to_xlsx, write_xlsx, ConvertOptions};

pub fn convert_to_xlsx(
    source_path: &Path,
    output_path: Option<&Path>,
    options: ConvertOptions,
) -> Result<PathBuf, ConvertError> {
    let extension = source_path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    let output = output_path
        .map(Path::to_path_buf)
        .unwrap_or_else(|| source_path.with_extension("xlsx"));

    match extension.as_str() {
        "csv" => convert_csv_to_xlsx(source_path, &output, options),
        "xlsx" => {
            if source_path != output {
                std::fs::copy(source_path, &output).map_err(|source| ConvertError::Io {
                    path: output.clone(),
                    source,
                })?;
            }
            Ok(output)
        }
        "xls" => Err(ConvertError::UnsupportedFormat(
            ".xls conversion is provided by platform-windows".to_string(),
        )),
        other => Err(ConvertError::UnsupportedFormat(other.to_string())),
    }
}

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
