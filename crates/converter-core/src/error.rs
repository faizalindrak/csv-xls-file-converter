use std::path::PathBuf;

#[derive(Debug, thiserror::Error)]
pub enum ConvertError {
    #[error("unsupported file format '{0}'. Use CSV or XLS")]
    UnsupportedFormat(String),
    #[error("failed to read CSV file: {0}")]
    CsvRead(String),
    #[error("failed to write XLSX file: {0}")]
    XlsxWrite(String),
    #[error("I/O error for {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
}
