use chrono::NaiveDate;
use converter_core::{detect_date_format_for_column, parse_date_value, DateFormat};

#[test]
fn detects_unambiguous_dmy_and_mdy_columns() {
    assert_eq!(
        detect_date_format_for_column(&["13/02/2024", "28/02/2024"]),
        Some(DateFormat::Dmy)
    );
    assert_eq!(
        detect_date_format_for_column(&["02/13/2024", "02/28/2024"]),
        Some(DateFormat::Mdy)
    );
}

#[test]
fn ambiguous_dates_default_to_dmy() {
    assert_eq!(
        detect_date_format_for_column(&["01/02/2024", "03/04/2024"]),
        Some(DateFormat::Dmy)
    );
}

#[test]
fn parses_two_digit_years_like_python() {
    assert_eq!(
        parse_date_value("01/02/24", DateFormat::Dmy),
        NaiveDate::from_ymd_opt(2024, 2, 1)
    );
    assert_eq!(
        parse_date_value("01/02/75", DateFormat::Dmy),
        NaiveDate::from_ymd_opt(1975, 2, 1)
    );
}
