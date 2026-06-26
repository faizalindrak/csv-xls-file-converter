use std::fs;

use converter_cli::monitor::{
    discover_existing_files, matches_exclude_keyword, output_path_for, should_process,
};
use tempfile::tempdir;

#[test]
fn file_format_filter_respects_profile_formats() {
    assert!(should_process("report.csv", &["csv".to_string()], ""));
    assert!(!should_process("report.xls", &["csv".to_string()], ""));
    assert!(should_process("report.XLS", &["xls".to_string()], ""));
}

#[test]
fn exclude_keywords_skip_matching_names() {
    assert!(!should_process(
        "invoice_backup.csv",
        &["csv".to_string()],
        "temp, backup"
    ));
    assert!(matches_exclude_keyword("draft-report.csv", "draft"));
}

#[test]
fn output_path_uses_requested_folder_or_source_folder() {
    let same_folder = output_path_for("C:\\inbox\\report.csv", None);
    let output_folder = output_path_for("C:\\inbox\\report.csv", Some("D:\\out"));

    assert_eq!(same_folder.to_string_lossy(), "C:\\inbox\\report.xlsx");
    assert_eq!(output_folder.to_string_lossy(), "D:\\out\\report.xlsx");
}

#[test]
fn discover_existing_files_respects_formats_and_exclusions() {
    let dir = tempdir().expect("temp dir should be created");
    fs::write(dir.path().join("keep.csv"), "a,b\n1,2\n").expect("fixture should be written");
    fs::write(dir.path().join("skip.xls"), "").expect("fixture should be written");
    fs::write(dir.path().join("note.txt"), "").expect("fixture should be written");

    let files = discover_existing_files(dir.path(), &["csv".to_string()], "skip")
        .expect("discovery should succeed");

    assert_eq!(files.len(), 1);
    assert_eq!(
        files[0].file_name().and_then(|name| name.to_str()),
        Some("keep.csv")
    );
}
