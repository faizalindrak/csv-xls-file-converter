use converter_core::{clean_numeric, sanitize_for_xlsx_cell, CellValue};

#[test]
fn preserves_non_finite_tokens_as_text() {
    assert_eq!(clean_numeric("NAN"), CellValue::Text("NAN".to_string()));
    assert_eq!(clean_numeric("INF"), CellValue::Text("INF".to_string()));
    assert_eq!(clean_numeric("-INF"), CellValue::Text("-INF".to_string()));
}

#[test]
fn preserves_leading_zero_strings() {
    assert_eq!(clean_numeric("007"), CellValue::Text("007".to_string()));
}

#[test]
fn converts_finite_numbers() {
    assert_eq!(clean_numeric("12.5"), CellValue::Number(12.5));
    assert_eq!(clean_numeric("12,5"), CellValue::Number(12.5));
}

#[test]
fn sanitizes_xml_and_formula_prefixes() {
    assert_eq!(sanitize_for_xlsx_cell("a\u{0000}b"), "ab");
    assert_eq!(sanitize_for_xlsx_cell("=SUM(A1:A2)"), "'=SUM(A1:A2)");
    assert_eq!(sanitize_for_xlsx_cell("@cmd"), "'@cmd");
}
