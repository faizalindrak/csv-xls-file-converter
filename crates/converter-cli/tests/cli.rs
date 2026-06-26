use std::fs;
use std::process::Command;

use tempfile::tempdir;

#[test]
fn prints_help_without_arguments() {
    let output = Command::new(env!("CARGO_BIN_EXE_csv-xls-converter"))
        .output()
        .expect("binary should run");

    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).expect("stdout should be UTF-8");
    assert!(stdout.contains("Convert CSV/XLS files"));
}

#[test]
fn fails_for_missing_input_file() {
    let output = Command::new(env!("CARGO_BIN_EXE_csv-xls-converter"))
        .arg("missing.csv")
        .output()
        .expect("binary should run");

    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).expect("stderr should be UTF-8");
    assert!(stderr.contains("File not found"));
}

#[test]
fn converts_csv_file() {
    let dir = tempdir().expect("temp dir should be created");
    let input = dir.path().join("input.csv");
    let output = dir.path().join("output.xlsx");
    fs::write(&input, "name,value\na,1\n").expect("fixture should be written");

    let status = Command::new(env!("CARGO_BIN_EXE_csv-xls-converter"))
        .arg(&input)
        .arg("--output")
        .arg(&output)
        .status()
        .expect("binary should run");

    assert!(status.success());
    assert!(output.exists());
}
