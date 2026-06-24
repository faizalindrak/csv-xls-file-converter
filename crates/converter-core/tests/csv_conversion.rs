use std::fs;

use converter_core::{convert_to_xlsx, read_csv, ConvertOptions};
use tempfile::tempdir;

#[test]
fn reads_semicolon_csv_and_pads_rows() {
    let dir = tempdir().expect("temp dir should be created");
    let input = dir.path().join("sample.csv");
    fs::write(&input, "a;b;c\n1;2\n3;4;5\n").expect("fixture should be written");

    let table = read_csv(&input, false).expect("CSV should parse");

    assert_eq!(table.header, vec!["a", "b", "c"]);
    assert_eq!(table.rows[0].cells.len(), 3);
    assert_eq!(table.rows[0].cells[2].raw, "");
}

#[test]
fn converts_csv_with_non_finite_tokens() {
    let dir = tempdir().expect("temp dir should be created");
    let input = dir.path().join("non_finite.csv");
    let output = dir.path().join("non_finite.xlsx");
    fs::write(&input, "label,value\nalpha,NAN\nbeta,INF\ngamma,-INF\n")
        .expect("fixture should be written");

    let result = convert_to_xlsx(
        &input,
        Some(&output),
        ConvertOptions {
            remove_backticks: false,
            auto_detect_dates: false,
        },
    )
    .expect("CSV should convert");

    assert_eq!(result, output);
    assert!(output.exists());
}
