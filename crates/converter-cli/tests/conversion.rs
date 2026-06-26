use std::path::{Path, PathBuf};

use converter_cli::conversion::{
    conversion_backend_for, output_path_for_conversion, ConversionBackend,
};

#[test]
fn legacy_xls_files_use_platform_backend() {
    let backend = conversion_backend_for(Path::new("report.XLS"));

    assert_eq!(backend, ConversionBackend::LegacyXls);
}

#[test]
fn csv_and_xlsx_files_use_core_backend() {
    assert_eq!(
        conversion_backend_for(Path::new("report.csv")),
        ConversionBackend::Core
    );
    assert_eq!(
        conversion_backend_for(Path::new("report.xlsx")),
        ConversionBackend::Core
    );
}

#[test]
fn output_path_defaults_to_xlsx_extension() {
    let output = output_path_for_conversion(Path::new("C:\\inbox\\report.xls"), None);

    assert_eq!(output, PathBuf::from("C:\\inbox\\report.xlsx"));
}

#[test]
fn explicit_output_path_is_preserved() {
    let requested = Path::new("D:\\out\\converted.xlsx");
    let output = output_path_for_conversion(Path::new("C:\\inbox\\report.xls"), Some(requested));

    assert_eq!(output, PathBuf::from("D:\\out\\converted.xlsx"));
}
