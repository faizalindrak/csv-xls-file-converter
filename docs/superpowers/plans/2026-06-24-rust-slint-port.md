# Rust/Slint Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full Rust/Slint replacement for the Python CSV/XLS Converter while preserving CLI behavior, GUI workflows, monitoring, Windows integrations, and AppData config/history compatibility.

**Architecture:** Create a Cargo workspace with focused crates for conversion, app state, Windows platform helpers, CLI, and Slint GUI. Keep Python files as behavioral reference during the migration, but make the Rust executable the release target after parity checks pass.

**Tech Stack:** Rust 2021, Slint 1.16, `slint-build`, `clap`, `serde`, `serde_json`, `csv`, `encoding_rs`, `regex`, `chrono`, `rust_xlsxwriter`, `notify`, `thiserror`, `uuid`, `dirs`, `windows`, `tray-icon`, `assert_cmd`, `predicates`, `tempfile`.

---

## File Structure

- Create `Cargo.toml`: workspace members and shared dependency versions.
- Create `.cargo/config.toml`: optional Windows target settings if needed by Slint builds.
- Create `crates/converter-core/Cargo.toml`: pure conversion crate.
- Create `crates/converter-core/src/lib.rs`: public conversion API.
- Create `crates/converter-core/src/error.rs`: structured conversion errors.
- Create `crates/converter-core/src/sanitize.rs`: XML cleanup, formula escaping, Excel cell limits.
- Create `crates/converter-core/src/numeric.rs`: numeric cleanup and non-finite preservation.
- Create `crates/converter-core/src/dates.rs`: date format detection and parsing.
- Create `crates/converter-core/src/csv_reader.rs`: encoding, delimiter, row normalization.
- Create `crates/converter-core/src/xlsx_writer.rs`: XLSX writing for CSV data.
- Create `crates/app-state/Cargo.toml`: persistence crate.
- Create `crates/app-state/src/lib.rs`: config/history paths and public exports.
- Create `crates/app-state/src/models.rs`: profile/settings/history structs.
- Create `crates/app-state/src/store.rs`: JSON load/save helpers.
- Create `crates/platform-windows/Cargo.toml`: Windows helpers crate.
- Create `crates/platform-windows/src/lib.rs`: cross-platform stubs plus Windows modules.
- Create `crates/platform-windows/src/xls.rs`: VBScript/cscript Excel conversion.
- Create `crates/platform-windows/src/registry.rs`: startup and context menu registry.
- Create `crates/platform-windows/src/notification.rs`: silent-mode notifications.
- Create `crates/converter-cli/Cargo.toml`: CLI binary crate.
- Create `crates/converter-cli/src/main.rs`: argument parsing and command dispatch.
- Create `crates/converter-cli/src/monitor.rs`: CLI folder monitoring.
- Create `crates/converter-gui/Cargo.toml`: Slint GUI crate.
- Create `crates/converter-gui/build.rs`: compile `ui/main.slint`.
- Create `crates/converter-gui/src/main.rs`: app startup and callback wiring.
- Create `crates/converter-gui/src/controller.rs`: GUI state and background task bridge.
- Create `crates/converter-gui/src/models.rs`: Slint model conversion.
- Create `crates/converter-gui/src/monitor.rs`: GUI monitor workers.
- Create `crates/converter-gui/ui/main.slint`: root app shell.
- Create `crates/converter-gui/ui/widgets.slint`: reusable Slint widgets.
- Create `tests/fixtures/`: sample CSV fixtures shared by integration tests.
- Modify `build.bat`: build Rust executable and installer.
- Modify `.github/workflows/build.yml`: build and package Rust executable.
- Modify `installer.iss`: point to Rust output executable.
- Modify `README.md`: update setup/build instructions.
- Modify `CHANGELOG.md`: add migration entry when implementation is complete.

## Task 1: Scaffold The Rust Workspace

**Files:**
- Create: `Cargo.toml`
- Create: `crates/converter-core/Cargo.toml`
- Create: `crates/converter-core/src/lib.rs`
- Create: `crates/app-state/Cargo.toml`
- Create: `crates/app-state/src/lib.rs`
- Create: `crates/platform-windows/Cargo.toml`
- Create: `crates/platform-windows/src/lib.rs`
- Create: `crates/converter-cli/Cargo.toml`
- Create: `crates/converter-cli/src/main.rs`
- Create: `crates/converter-gui/Cargo.toml`
- Create: `crates/converter-gui/build.rs`
- Create: `crates/converter-gui/src/main.rs`
- Create: `crates/converter-gui/ui/main.slint`

- [ ] **Step 1: Add the workspace manifest**

Create `Cargo.toml`:

```toml
[workspace]
members = [
    "crates/app-state",
    "crates/converter-cli",
    "crates/converter-core",
    "crates/converter-gui",
    "crates/platform-windows",
]
resolver = "2"

[workspace.package]
edition = "2021"
license = "MIT"
version = "0.4.23"

[workspace.dependencies]
anyhow = "1"
assert_cmd = "2"
chrono = { version = "0.4", default-features = false, features = ["clock", "serde"] }
clap = { version = "4", features = ["derive"] }
csv = "1"
dirs = "6"
encoding_rs = "0.8"
notify = "8"
predicates = "3"
regex = "1"
rust_xlsxwriter = { version = "0.90", features = ["chrono"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
slint = "1.16.0"
slint-build = "1.16.0"
tempfile = "3"
thiserror = "2"
uuid = { version = "1", features = ["v4", "serde"] }
windows = { version = "0.61", features = ["Win32_System_Com", "Win32_UI_Shell", "Win32_UI_WindowsAndMessaging"] }
```

- [ ] **Step 2: Add minimal crate manifests and entry points**

Create `crates/converter-core/Cargo.toml`:

```toml
[package]
name = "converter-core"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
chrono.workspace = true
csv.workspace = true
encoding_rs.workspace = true
regex.workspace = true
rust_xlsxwriter.workspace = true
thiserror.workspace = true
```

Create `crates/converter-core/src/lib.rs`:

```rust
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
```

Create `crates/app-state/Cargo.toml`:

```toml
[package]
name = "app-state"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
dirs.workspace = true
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true
uuid.workspace = true
```

Create `crates/app-state/src/lib.rs`:

```rust
pub fn app_name() -> &'static str {
    "csv-xls-converter"
}
```

Create `crates/platform-windows/Cargo.toml`:

```toml
[package]
name = "platform-windows"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
thiserror.workspace = true

[target.'cfg(windows)'.dependencies]
windows.workspace = true
```

Create `crates/platform-windows/src/lib.rs`:

```rust
pub fn is_windows_feature_available() -> bool {
    cfg!(windows)
}
```

Create `crates/converter-cli/Cargo.toml`:

```toml
[package]
name = "converter-cli"
edition.workspace = true
license.workspace = true
version.workspace = true

[[bin]]
name = "csv-xls-converter"
path = "src/main.rs"

[dependencies]
app-state = { path = "../app-state" }
clap.workspace = true
converter-core = { path = "../converter-core" }
platform-windows = { path = "../platform-windows" }
```

Create `crates/converter-cli/src/main.rs`:

```rust
fn main() {
    println!("CSV/XLS Converter {}", converter_core::version());
}
```

Create `crates/converter-gui/Cargo.toml`:

```toml
[package]
name = "converter-gui"
edition.workspace = true
license.workspace = true
version.workspace = true
build = "build.rs"

[[bin]]
name = "csv-xls-converter-gui"
path = "src/main.rs"

[dependencies]
app-state = { path = "../app-state" }
converter-core = { path = "../converter-core" }
platform-windows = { path = "../platform-windows" }
slint.workspace = true

[build-dependencies]
slint-build.workspace = true
```

Create `crates/converter-gui/build.rs`:

```rust
fn main() {
    slint_build::compile("ui/main.slint").expect("failed to compile Slint UI");
}
```

Create `crates/converter-gui/src/main.rs`:

```rust
slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    AppWindow::new()?.run()
}
```

Create `crates/converter-gui/ui/main.slint`:

```slint
import { VerticalBox, Text } from "std-widgets.slint";

export component AppWindow inherits Window {
    title: "CSV/XLS Converter";
    width: 960px;
    height: 640px;

    VerticalBox {
        alignment: start;
        Text {
            text: "CSV/XLS Converter";
            font-size: 24px;
        }
    }
}
```

- [ ] **Step 3: Verify the workspace builds**

Run:

```powershell
rtk cargo check --workspace
```

Expected: Cargo resolves dependencies and all crates compile.

- [ ] **Step 4: Commit the scaffold**

```powershell
rtk git add Cargo.toml crates
rtk git commit -m "feat: scaffold rust slint workspace"
```

## Task 2: Implement AppData State Compatibility

**Files:**
- Create: `crates/app-state/src/models.rs`
- Create: `crates/app-state/src/store.rs`
- Modify: `crates/app-state/src/lib.rs`
- Test: `crates/app-state/tests/compat.rs`

- [ ] **Step 1: Write compatibility tests**

Create `crates/app-state/tests/compat.rs`:

```rust
use app_state::{GlobalSettings, MonitorProfile, ProfileDocument, SingleFileSettings};

#[test]
fn loads_existing_profile_json_shape() {
    let raw = r#"{
        "profiles": [{
            "id": "profile-1",
            "name": "Invoices",
            "watch_folder": "C:\\Input",
            "output_folder": "C:\\Output",
            "enabled": true,
            "delete_source": false,
            "process_existing": true,
            "auto_detect_dates": false,
            "file_formats": ["csv"],
            "exclude_keywords": "temp,backup"
        }],
        "single_file_settings": {
            "last_input_dir": "C:\\Docs",
            "last_output_dir": "C:\\Out",
            "remove_backticks": true,
            "auto_detect_dates": true,
            "delete_source": false
        },
        "global_settings": { "auto_startup": true },
        "future_field": "ignored"
    }"#;

    let doc: ProfileDocument = serde_json::from_str(raw).unwrap();

    assert_eq!(doc.profiles[0].name, "Invoices");
    assert_eq!(doc.profiles[0].file_formats, vec!["csv"]);
    assert_eq!(doc.profiles[0].exclude_keywords, "temp,backup");
    assert!(doc.single_file_settings.remove_backticks);
    assert!(doc.global_settings.auto_startup);
}

#[test]
fn defaults_match_python_models() {
    let profile = MonitorProfile::default();
    let single = SingleFileSettings::default();
    let global = GlobalSettings::default();

    assert_eq!(profile.name, "New Profile");
    assert_eq!(profile.file_formats, vec!["csv", "xls"]);
    assert!(profile.process_existing);
    assert!(!single.delete_source);
    assert!(!global.auto_startup);
}
```

- [ ] **Step 2: Verify tests fail before implementation**

Run:

```powershell
rtk cargo test -p app-state --test compat
```

Expected: FAIL because the exported models do not exist.

- [ ] **Step 3: Add state models**

Create `crates/app-state/src/models.rs`:

```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct MonitorProfile {
    pub id: String,
    pub name: String,
    pub watch_folder: String,
    pub output_folder: String,
    pub enabled: bool,
    pub delete_source: bool,
    pub process_existing: bool,
    pub auto_detect_dates: bool,
    pub file_formats: Vec<String>,
    pub exclude_keywords: String,
}

impl Default for MonitorProfile {
    fn default() -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            name: "New Profile".to_string(),
            watch_folder: String::new(),
            output_folder: String::new(),
            enabled: false,
            delete_source: false,
            process_existing: true,
            auto_detect_dates: false,
            file_formats: vec!["csv".to_string(), "xls".to_string()],
            exclude_keywords: String::new(),
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct SingleFileSettings {
    pub last_input_dir: String,
    pub last_output_dir: String,
    pub remove_backticks: bool,
    pub auto_detect_dates: bool,
    pub delete_source: bool,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct GlobalSettings {
    pub auto_startup: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(default)]
pub struct ConversionHistoryItem {
    pub source_path: String,
    pub output_path: String,
    pub status: String,
    pub timestamp: f64,
    pub error_message: String,
}

impl Default for ConversionHistoryItem {
    fn default() -> Self {
        Self {
            source_path: String::new(),
            output_path: String::new(),
            status: String::new(),
            timestamp: 0.0,
            error_message: String::new(),
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct ProfileDocument {
    pub profiles: Vec<MonitorProfile>,
    pub single_file_settings: SingleFileSettings,
    pub global_settings: GlobalSettings,
}
```

Create `crates/app-state/src/store.rs`:

```rust
use std::fs;
use std::path::PathBuf;

use crate::{ConversionHistoryItem, ProfileDocument};

#[derive(Debug, thiserror::Error)]
pub enum StateError {
    #[error("could not find an application config directory")]
    MissingConfigDir,
    #[error("I/O error for {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("JSON error for {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },
}

pub fn config_dir() -> Result<PathBuf, StateError> {
    let base = dirs::config_dir().ok_or(StateError::MissingConfigDir)?;
    Ok(base.join("csv-xls-converter"))
}

pub fn profiles_path() -> Result<PathBuf, StateError> {
    Ok(config_dir()?.join("profiles.json"))
}

pub fn history_path() -> Result<PathBuf, StateError> {
    Ok(config_dir()?.join("conversion_history.json"))
}

pub fn load_profiles_from(path: PathBuf) -> Result<ProfileDocument, StateError> {
    if !path.exists() {
        return Ok(ProfileDocument::default());
    }
    let text = fs::read_to_string(&path).map_err(|source| StateError::Io {
        path: path.clone(),
        source,
    })?;
    serde_json::from_str(&text).map_err(|source| StateError::Json { path, source })
}

pub fn save_profiles_to(path: PathBuf, doc: &ProfileDocument) -> Result<(), StateError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| StateError::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }
    let text = serde_json::to_string_pretty(doc)
        .map_err(|source| StateError::Json { path: path.clone(), source })?;
    fs::write(&path, text).map_err(|source| StateError::Io { path, source })
}

pub fn load_history_from(path: PathBuf) -> Result<Vec<ConversionHistoryItem>, StateError> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let text = fs::read_to_string(&path).map_err(|source| StateError::Io {
        path: path.clone(),
        source,
    })?;
    serde_json::from_str(&text).map_err(|source| StateError::Json { path, source })
}
```

Modify `crates/app-state/src/lib.rs`:

```rust
mod models;
mod store;

pub use models::{
    ConversionHistoryItem, GlobalSettings, MonitorProfile, ProfileDocument, SingleFileSettings,
};
pub use store::{
    config_dir, history_path, load_history_from, load_profiles_from, profiles_path,
    save_profiles_to, StateError,
};

pub fn app_name() -> &'static str {
    "csv-xls-converter"
}
```

- [ ] **Step 4: Verify app-state tests pass**

Run:

```powershell
rtk cargo test -p app-state
```

Expected: PASS.

- [ ] **Step 5: Commit app-state compatibility**

```powershell
rtk git add crates/app-state
rtk git commit -m "feat: preserve app state compatibility"
```

## Task 3: Port Core Sanitization, Numeric Cleanup, And Dates

**Files:**
- Create: `crates/converter-core/src/error.rs`
- Create: `crates/converter-core/src/sanitize.rs`
- Create: `crates/converter-core/src/numeric.rs`
- Create: `crates/converter-core/src/dates.rs`
- Modify: `crates/converter-core/src/lib.rs`
- Test: `crates/converter-core/tests/cell_rules.rs`
- Test: `crates/converter-core/tests/date_rules.rs`

- [ ] **Step 1: Write cell rule tests**

Create `crates/converter-core/tests/cell_rules.rs`:

```rust
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
```

- [ ] **Step 2: Write date tests**

Create `crates/converter-core/tests/date_rules.rs`:

```rust
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
        Some(NaiveDate::from_ymd_opt(2024, 2, 1).unwrap())
    );
    assert_eq!(
        parse_date_value("01/02/75", DateFormat::Dmy),
        Some(NaiveDate::from_ymd_opt(1975, 2, 1).unwrap())
    );
}
```

- [ ] **Step 3: Verify tests fail**

Run:

```powershell
rtk cargo test -p converter-core --test cell_rules --test date_rules
```

Expected: FAIL because the functions and types are not implemented.

- [ ] **Step 4: Implement core helpers**

Create `crates/converter-core/src/error.rs`:

```rust
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
        path: std::path::PathBuf,
        #[source]
        source: std::io::Error,
    },
}
```

Create `crates/converter-core/src/sanitize.rs`:

```rust
pub const EXCEL_MAX_CELL_CHARS: usize = 32_767;
const FORMULA_PREFIXES: [char; 4] = ['=', '+', '-', '@'];

pub fn sanitize_for_xml(value: &str) -> String {
    value
        .chars()
        .filter(|ch| !matches!(*ch as u32, 0x00..=0x08 | 0x0b | 0x0c | 0x0e..=0x1f))
        .collect()
}

pub fn sanitize_for_xlsx_cell(value: &str) -> String {
    let mut sanitized = sanitize_for_xml(value);
    if sanitized
        .chars()
        .next()
        .is_some_and(|ch| FORMULA_PREFIXES.contains(&ch))
    {
        sanitized.insert(0, '\'');
    }
    if sanitized.chars().count() > EXCEL_MAX_CELL_CHARS {
        sanitized = sanitized.chars().take(EXCEL_MAX_CELL_CHARS).collect();
    }
    sanitized
}
```

Create `crates/converter-core/src/numeric.rs`:

```rust
#[derive(Clone, Debug, PartialEq)]
pub enum CellValue {
    Text(String),
    Number(f64),
}

pub fn clean_numeric(input: &str) -> CellValue {
    let s = input.trim();
    if s.is_empty() || s.starts_with('`') {
        return CellValue::Text(s.to_string());
    }
    if s.len() > 1 && s.as_bytes()[0] == b'0' && s.as_bytes()[1].is_ascii_digit() {
        return CellValue::Text(s.to_string());
    }

    let candidates = [
        s.to_string(),
        s.replace(',', "."),
        s.replace('.', "").replace(',', "."),
        s.replace(',', ""),
    ];

    for candidate in candidates {
        if let Ok(number) = candidate.parse::<f64>() {
            if number.is_finite() {
                return CellValue::Number(number);
            }
            return CellValue::Text(s.to_string());
        }
    }

    CellValue::Text(s.to_string())
}
```

Create `crates/converter-core/src/dates.rs`:

```rust
use chrono::NaiveDate;
use regex::Regex;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DateFormat {
    Dmy,
    Mdy,
    Iso,
}

pub fn detect_date_format_for_column(values: &[&str]) -> Option<DateFormat> {
    let iso = Regex::new(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$").unwrap();
    let ambiguous = Regex::new(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$").unwrap();
    let mut dmy_score = 0;
    let mut mdy_score = 0;
    let mut iso_count = 0;
    let mut date_count = 0;

    for raw in values {
        let value = raw.trim();
        if value.is_empty() {
            continue;
        }
        if iso.is_match(value) {
            iso_count += 1;
            date_count += 1;
            continue;
        }
        if let Some(caps) = ambiguous.captures(value) {
            let first = caps[1].parse::<u32>().unwrap_or(0);
            let second = caps[2].parse::<u32>().unwrap_or(0);
            date_count += 1;
            if (13..=31).contains(&first) {
                dmy_score += 10;
            } else if (13..=31).contains(&second) {
                mdy_score += 10;
            }
        }
    }

    if date_count == 0 {
        return None;
    }
    if (iso_count as f64) > (date_count as f64 * 0.5) {
        return Some(DateFormat::Iso);
    }
    if dmy_score > mdy_score {
        Some(DateFormat::Dmy)
    } else if mdy_score > dmy_score {
        Some(DateFormat::Mdy)
    } else {
        Some(DateFormat::Dmy)
    }
}

pub fn parse_date_value(value: &str, format: DateFormat) -> Option<NaiveDate> {
    let value = value.trim();
    if value.is_empty() {
        return None;
    }

    match format {
        DateFormat::Iso => {
            let re = Regex::new(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$").unwrap();
            let caps = re.captures(value)?;
            NaiveDate::from_ymd_opt(
                caps[1].parse().ok()?,
                caps[2].parse().ok()?,
                caps[3].parse().ok()?,
            )
        }
        DateFormat::Dmy | DateFormat::Mdy => {
            let re = Regex::new(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$").unwrap();
            let caps = re.captures(value)?;
            let first = caps[1].parse::<u32>().ok()?;
            let second = caps[2].parse::<u32>().ok()?;
            let mut year = caps[3].parse::<i32>().ok()?;
            if year < 100 {
                year = if year < 50 { 2000 + year } else { 1900 + year };
            }
            let (day, month) = match format {
                DateFormat::Dmy => (first, second),
                DateFormat::Mdy => (second, first),
                DateFormat::Iso => unreachable!(),
            };
            NaiveDate::from_ymd_opt(year, month, day)
        }
    }
}
```

Modify `crates/converter-core/src/lib.rs`:

```rust
mod dates;
mod error;
mod numeric;
mod sanitize;

pub use dates::{detect_date_format_for_column, parse_date_value, DateFormat};
pub use error::ConvertError;
pub use numeric::{clean_numeric, CellValue};
pub use sanitize::{sanitize_for_xlsx_cell, sanitize_for_xml, EXCEL_MAX_CELL_CHARS};

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
```

- [ ] **Step 5: Verify core helper tests pass**

Run:

```powershell
rtk cargo test -p converter-core
```

Expected: PASS.

- [ ] **Step 6: Commit core helpers**

```powershell
rtk git add crates/converter-core
rtk git commit -m "feat: port conversion cell rules"
```

## Task 4: Port CSV Reading And XLSX Writing

**Files:**
- Create: `crates/converter-core/src/csv_reader.rs`
- Create: `crates/converter-core/src/xlsx_writer.rs`
- Modify: `crates/converter-core/src/lib.rs`
- Test: `crates/converter-core/tests/csv_conversion.rs`

- [ ] **Step 1: Write CSV conversion tests**

Create `crates/converter-core/tests/csv_conversion.rs`:

```rust
use std::fs;

use converter_core::{convert_to_xlsx, read_csv, ConvertOptions};
use tempfile::tempdir;

#[test]
fn reads_semicolon_csv_and_pads_rows() {
    let dir = tempdir().unwrap();
    let input = dir.path().join("sample.csv");
    fs::write(&input, "a;b;c\n1;2\n3;4;5\n").unwrap();

    let table = read_csv(&input, false).unwrap();

    assert_eq!(table.header, vec!["a", "b", "c"]);
    assert_eq!(table.rows[0].cells.len(), 3);
    assert_eq!(table.rows[0].cells[2].raw, "");
}

#[test]
fn converts_csv_with_non_finite_tokens() {
    let dir = tempdir().unwrap();
    let input = dir.path().join("non_finite.csv");
    let output = dir.path().join("non_finite.xlsx");
    fs::write(&input, "label,value\nalpha,NAN\nbeta,INF\ngamma,-INF\n").unwrap();

    let result = convert_to_xlsx(
        &input,
        Some(&output),
        ConvertOptions {
            remove_backticks: false,
            auto_detect_dates: false,
        },
    )
    .unwrap();

    assert_eq!(result, output);
    assert!(output.exists());
}
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
rtk cargo test -p converter-core --test csv_conversion
```

Expected: FAIL because `read_csv`, `convert_to_xlsx`, and `ConvertOptions` do not exist.

- [ ] **Step 3: Implement CSV reader and XLSX writer**

Create `crates/converter-core/src/csv_reader.rs`:

```rust
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
                .map(|line| line.as_bytes().iter().filter(|byte| *byte == candidate).count())
                .sum::<usize>()
        })
        .filter(|candidate| {
            sample
                .iter()
                .any(|line| line.as_bytes().contains(candidate))
        })
        .unwrap_or(b',')
}
```

Create `crates/converter-core/src/xlsx_writer.rs`:

```rust
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use chrono::NaiveDateTime;
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
    worksheet
        .set_name("Sheet1")
        .map_err(map_xlsx_error)?;

    let text_format = Format::new().set_num_format("@");
    let date_format = Format::new().set_num_format("yyyy-mm-dd");
    let date_columns = if auto_detect_dates {
        analyze_date_columns(table)
    } else {
        BTreeMap::new()
    };
    let mut max_lengths: Vec<usize> = table.header.iter().map(|h| h.len()).collect();

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
                    let datetime = NaiveDateTime::new(date, Default::default());
                    worksheet
                        .write_datetime_with_format(excel_row, col as u16, datetime, &date_format)
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
            }
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
            .map(|row| row.cells.get(col).map(|cell| cell.raw.as_str()).unwrap_or(""))
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
```

Modify `crates/converter-core/src/lib.rs`:

```rust
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
```

- [ ] **Step 4: Verify CSV conversion tests pass**

Run:

```powershell
rtk cargo test -p converter-core
```

Expected: PASS.

- [ ] **Step 5: Commit CSV/XLSX core**

```powershell
rtk git add crates/converter-core
rtk git commit -m "feat: port csv to xlsx conversion"
```

## Task 5: Add Windows Platform Helpers

**Files:**
- Create: `crates/platform-windows/src/xls.rs`
- Create: `crates/platform-windows/src/registry.rs`
- Create: `crates/platform-windows/src/notification.rs`
- Modify: `crates/platform-windows/src/lib.rs`
- Test: `crates/platform-windows/tests/platform.rs`

- [ ] **Step 1: Write platform tests**

Create `crates/platform-windows/tests/platform.rs`:

```rust
use platform_windows::{context_menu_command, create_vbs_script};

#[test]
fn vbs_script_uses_excel_save_as_xlsx_format() {
    let script = create_vbs_script();
    assert!(script.contains("CreateObject(\"Excel.Application\")"));
    assert!(script.contains("SaveAs strXLSXFile, 51"));
}

#[test]
fn context_menu_command_uses_silent_mode() {
    let command = context_menu_command("C:\\Program Files\\CSV-XLS-Converter.exe");
    assert!(command.contains("--silent"));
    assert!(command.contains("\"%1\""));
}
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
rtk cargo test -p platform-windows
```

Expected: FAIL because helper functions are missing.

- [ ] **Step 3: Implement Windows helper modules**

Create `crates/platform-windows/src/xls.rs`:

```rust
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, thiserror::Error)]
pub enum PlatformError {
    #[error("{0}")]
    Message(String),
    #[error("I/O error for {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
}

pub fn create_vbs_script() -> &'static str {
    r#"
Set objExcel = CreateObject("Excel.Application")
objExcel.Visible = False
objExcel.DisplayAlerts = False
On Error Resume Next
strXLSFile = WScript.Arguments(0)
strXLSXFile = WScript.Arguments(1)
Set objWorkbook = objExcel.Workbooks.Open(strXLSFile)
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to open XLS file: " & Err.Description
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.SaveAs strXLSXFile, 51
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to save as XLSX: " & Err.Description
    objWorkbook.Close False
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.Close False
objExcel.Quit
WScript.Quit(0)
"#
}

pub fn convert_xls_to_xlsx(source: &Path, output: &Path) -> Result<PathBuf, PlatformError> {
    if !cfg!(windows) {
        return Err(PlatformError::Message(
            "XLS conversion requires Windows with Microsoft Excel installed".to_string(),
        ));
    }
    let script_path = std::env::temp_dir().join("csv_xls_converter_temp_convert.vbs");
    fs::write(&script_path, create_vbs_script()).map_err(|source| PlatformError::Io {
        path: script_path.clone(),
        source,
    })?;
    let status = Command::new("cscript")
        .arg("//Nologo")
        .arg(&script_path)
        .arg(source)
        .arg(output)
        .status()
        .map_err(|source| PlatformError::Io {
            path: script_path.clone(),
            source,
        })?;
    let _ = fs::remove_file(&script_path);
    if status.success() {
        Ok(output.to_path_buf())
    } else {
        Err(PlatformError::Message("Error converting XLS".to_string()))
    }
}
```

Create `crates/platform-windows/src/registry.rs`:

```rust
pub fn context_menu_command(executable_path: &str) -> String {
    format!("\"{executable_path}\" --silent \"%1\"")
}

pub fn startup_registry_name() -> &'static str {
    "CSV-XLS-Converter"
}

pub fn register_context_menu(_executable_path: &str) -> Result<(), crate::PlatformError> {
    if cfg!(windows) {
        Ok(())
    } else {
        Err(crate::PlatformError::Message(
            "Context menu registration is only available on Windows".to_string(),
        ))
    }
}
```

Create `crates/platform-windows/src/notification.rs`:

```rust
pub fn show_notification(title: &str, message: &str) -> Result<(), crate::PlatformError> {
    if cfg!(windows) {
        let _ = (title, message);
        Ok(())
    } else {
        Err(crate::PlatformError::Message(
            "Windows notifications are only available on Windows".to_string(),
        ))
    }
}
```

Modify `crates/platform-windows/src/lib.rs`:

```rust
mod notification;
mod registry;
mod xls;

pub use notification::show_notification;
pub use registry::{context_menu_command, register_context_menu, startup_registry_name};
pub use xls::{convert_xls_to_xlsx, create_vbs_script, PlatformError};

pub fn is_windows_feature_available() -> bool {
    cfg!(windows)
}
```

- [ ] **Step 4: Verify platform tests pass**

Run:

```powershell
rtk cargo test -p platform-windows
```

Expected: PASS.

- [ ] **Step 5: Commit Windows helpers**

```powershell
rtk git add crates/platform-windows
rtk git commit -m "feat: add windows platform helpers"
```

## Task 6: Implement The CLI

**Files:**
- Modify: `crates/converter-cli/src/main.rs`
- Create: `crates/converter-cli/src/monitor.rs`
- Test: `crates/converter-cli/tests/cli.rs`

- [ ] **Step 1: Write CLI tests**

Create `crates/converter-cli/tests/cli.rs`:

```rust
use assert_cmd::Command;
use predicates::prelude::*;

#[test]
fn prints_help_without_arguments() {
    let mut cmd = Command::cargo_bin("csv-xls-converter").unwrap();
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("Convert CSV/XLS files"));
}

#[test]
fn fails_for_missing_input_file() {
    let mut cmd = Command::cargo_bin("csv-xls-converter").unwrap();
    cmd.arg("missing.csv")
        .assert()
        .failure()
        .stderr(predicate::str::contains("File not found"));
}
```

- [ ] **Step 2: Verify CLI tests fail**

Run:

```powershell
rtk cargo test -p converter-cli --test cli
```

Expected: FAIL because CLI behavior is not implemented.

- [ ] **Step 3: Implement CLI arguments and dispatch**

Modify `crates/converter-cli/src/main.rs`:

```rust
use std::path::PathBuf;

use clap::Parser;
use converter_core::{convert_to_xlsx, ConvertOptions};

#[derive(Debug, Parser)]
#[command(
    name = "csv-xls-converter",
    about = "Convert CSV/XLS files to XLSX format with optional folder monitoring."
)]
struct Args {
    input: Option<PathBuf>,
    #[arg(short, long)]
    output: Option<PathBuf>,
    #[arg(long, value_name = "FOLDER")]
    monitor: Option<PathBuf>,
    #[arg(long)]
    delete_source: bool,
    #[arg(long)]
    skip_existing: bool,
    #[arg(long)]
    remove_backticks: bool,
    #[arg(long)]
    silent: bool,
    #[arg(long, value_name = "KEYWORDS")]
    exclude: Option<String>,
}

fn main() {
    let args = Args::parse();
    let code = run(args);
    std::process::exit(code);
}

fn run(args: Args) -> i32 {
    if let Some(folder) = args.monitor {
        eprintln!("Monitor mode is not wired yet: {}", folder.display());
        return 1;
    }

    let Some(input) = args.input else {
        let _ = Args::command().print_help();
        println!();
        return 0;
    };

    if !input.exists() {
        if !args.silent {
            eprintln!("Error: File not found: {}", input.display());
        }
        return 1;
    }

    let result = convert_to_xlsx(
        &input,
        args.output.as_deref(),
        ConvertOptions {
            remove_backticks: args.remove_backticks,
            auto_detect_dates: false,
        },
    );

    match result {
        Ok(path) => {
            if !args.silent {
                println!("Successfully converted to: {}", path.display());
            }
            0
        }
        Err(error) => {
            if !args.silent {
                eprintln!("Conversion failed: {error}");
            }
            1
        }
    }
}
```

- [ ] **Step 4: Add test dependencies**

Modify `crates/converter-cli/Cargo.toml`:

```toml
[package]
name = "converter-cli"
edition.workspace = true
license.workspace = true
version.workspace = true

[[bin]]
name = "csv-xls-converter"
path = "src/main.rs"

[dependencies]
app-state = { path = "../app-state" }
clap.workspace = true
converter-core = { path = "../converter-core" }
platform-windows = { path = "../platform-windows" }

[dev-dependencies]
assert_cmd.workspace = true
predicates.workspace = true
tempfile.workspace = true
```

- [ ] **Step 5: Verify CLI tests pass**

Run:

```powershell
rtk cargo test -p converter-cli
```

Expected: PASS.

- [ ] **Step 6: Commit CLI**

```powershell
rtk git add crates/converter-cli
rtk git commit -m "feat: add rust converter cli"
```

## Task 7: Implement Monitor Engine

**Files:**
- Create: `crates/converter-cli/src/monitor.rs`
- Create: `crates/converter-gui/src/monitor.rs`
- Test: `crates/converter-cli/tests/monitor_filters.rs`

- [ ] **Step 1: Write monitor filter tests**

Create `crates/converter-cli/tests/monitor_filters.rs`:

```rust
use converter_cli::monitor::{matches_exclude_keyword, should_process};

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
```

- [ ] **Step 2: Verify monitor tests fail**

Run:

```powershell
rtk cargo test -p converter-cli --test monitor_filters
```

Expected: FAIL because monitor module is not exported.

- [ ] **Step 3: Expose converter-cli as a library**

Modify `crates/converter-cli/Cargo.toml`:

```toml
[lib]
name = "converter_cli"
path = "src/lib.rs"
```

Create `crates/converter-cli/src/lib.rs`:

```rust
pub mod monitor;
```

Create `crates/converter-cli/src/monitor.rs`:

```rust
use std::path::Path;

pub fn matches_exclude_keyword(file_path: &str, exclude_keywords: &str) -> bool {
    if exclude_keywords.trim().is_empty() {
        return false;
    }
    let filename = Path::new(file_path)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(file_path)
        .to_ascii_lowercase();
    exclude_keywords
        .split(',')
        .map(|keyword| keyword.trim().to_ascii_lowercase())
        .filter(|keyword| !keyword.is_empty())
        .any(|keyword| filename.contains(&keyword))
}

pub fn should_process(file_path: &str, allowed_formats: &[String], exclude_keywords: &str) -> bool {
    let extension = Path::new(file_path)
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    allowed_formats
        .iter()
        .any(|allowed| allowed.eq_ignore_ascii_case(&extension))
        && !matches_exclude_keyword(file_path, exclude_keywords)
}
```

- [ ] **Step 4: Verify monitor filter tests pass**

Run:

```powershell
rtk cargo test -p converter-cli --test monitor_filters
```

Expected: PASS.

- [ ] **Step 5: Extend monitor module with notify-based event loop**

Add to `crates/converter-cli/src/monitor.rs`:

```rust
use std::sync::mpsc::channel;
use std::time::Duration;

use notify::{Config, EventKind, RecommendedWatcher, RecursiveMode, Watcher};

pub fn watch_folder_once(folder: &Path) -> notify::Result<RecommendedWatcher> {
    let (_tx, rx) = channel();
    let mut watcher = RecommendedWatcher::new(
        move |result| {
            let _ = _tx.send(result);
        },
        Config::default().with_poll_interval(Duration::from_secs(1)),
    )?;
    watcher.watch(folder, RecursiveMode::Recursive)?;
    drop(rx);
    Ok(watcher)
}

pub fn is_create_or_move(kind: &EventKind) -> bool {
    matches!(kind, EventKind::Create(_) | EventKind::Modify(_))
}
```

Add `notify.workspace = true` to `crates/converter-cli/Cargo.toml`.

- [ ] **Step 6: Run CLI tests**

Run:

```powershell
rtk cargo test -p converter-cli
```

Expected: PASS.

- [ ] **Step 7: Commit monitor filters**

```powershell
rtk git add crates/converter-cli
rtk git commit -m "feat: add rust monitor filtering"
```

## Task 8: Build The Slint GUI Shell

**Files:**
- Modify: `crates/converter-gui/ui/main.slint`
- Create: `crates/converter-gui/ui/widgets.slint`
- Create: `crates/converter-gui/src/controller.rs`
- Create: `crates/converter-gui/src/models.rs`
- Modify: `crates/converter-gui/src/main.rs`

- [ ] **Step 1: Replace minimal UI with app shell**

Create `crates/converter-gui/ui/widgets.slint`:

```slint
import { Button, CheckBox, LineEdit } from "std-widgets.slint";

export component PathPicker inherits Rectangle {
    in-out property <string> path;
    in property <string> placeholder;
    callback browse();
    height: 36px;

    HorizontalLayout {
        spacing: 8px;
        LineEdit {
            text <=> root.path;
            placeholder-text: root.placeholder;
        }
        Button {
            text: "Browse";
            clicked => { root.browse(); }
        }
    }
}

export component OptionCheck inherits CheckBox {
    min-height: 28px;
}
```

Modify `crates/converter-gui/ui/main.slint`:

```slint
import { Button, CheckBox, LineEdit, TabWidget, TextEdit } from "std-widgets.slint";
import { PathPicker } from "widgets.slint";

export component AppWindow inherits Window {
    in-out property <string> input-path;
    in-out property <string> output-folder;
    in-out property <bool> remove-backticks;
    in-out property <bool> auto-detect-dates;
    in-out property <bool> delete-source;
    in property <string> status-message;

    callback browse-input();
    callback browse-output();
    callback convert-file();

    title: "CSV/XLS Converter";
    width: 1040px;
    height: 720px;

    TabWidget {
        Tab {
            title: "Convert";
            VerticalLayout {
                padding: 16px;
                spacing: 12px;
                Text { text: "Convert Single File"; font-size: 22px; }
                PathPicker {
                    path <=> root.input-path;
                    placeholder: "Select CSV or XLS file";
                    browse => { root.browse-input(); }
                }
                PathPicker {
                    path <=> root.output-folder;
                    placeholder: "Output folder (optional)";
                    browse => { root.browse-output(); }
                }
                HorizontalLayout {
                    spacing: 16px;
                    CheckBox { text: "Remove backticks"; checked <=> root.remove-backticks; }
                    CheckBox { text: "Auto-detect dates"; checked <=> root.auto-detect-dates; }
                    CheckBox { text: "Delete original"; checked <=> root.delete-source; }
                }
                Button {
                    text: "Convert to XLSX";
                    clicked => { root.convert-file(); }
                }
                Text { text: root.status-message; }
            }
        }
        Tab {
            title: "Monitor";
            VerticalLayout { padding: 16px; Text { text: "Monitor profiles"; } }
        }
        Tab {
            title: "History";
            VerticalLayout { padding: 16px; Text { text: "Recent conversions"; } }
        }
        Tab {
            title: "Settings";
            VerticalLayout { padding: 16px; Text { text: "Settings"; } }
        }
    }
}
```

- [ ] **Step 2: Wire callbacks in Rust**

Create `crates/converter-gui/src/controller.rs`:

```rust
use std::path::PathBuf;

use converter_core::{convert_to_xlsx, ConvertOptions};

use crate::AppWindow;

pub fn wire_callbacks(app: &AppWindow) {
    let weak = app.as_weak();
    app.on_convert_file(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let input = PathBuf::from(app.get_input_path().to_string());
        let output_folder = app.get_output_folder().to_string();
        let output = if output_folder.trim().is_empty() {
            None
        } else {
            let filename = input
                .file_stem()
                .and_then(|stem| stem.to_str())
                .map(|stem| format!("{stem}.xlsx"))
                .unwrap_or_else(|| "output.xlsx".to_string());
            Some(PathBuf::from(output_folder).join(filename))
        };
        let result = convert_to_xlsx(
            &input,
            output.as_deref(),
            ConvertOptions {
                remove_backticks: app.get_remove_backticks(),
                auto_detect_dates: app.get_auto_detect_dates(),
            },
        );
        match result {
            Ok(path) => app.set_status_message(format!("Converted: {}", path.display()).into()),
            Err(error) => app.set_status_message(format!("Conversion failed: {error}").into()),
        }
    });
}
```

Modify `crates/converter-gui/src/main.rs`:

```rust
mod controller;

slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    let app = AppWindow::new()?;
    controller::wire_callbacks(&app);
    app.run()
}
```

- [ ] **Step 3: Verify GUI crate compiles**

Run:

```powershell
rtk cargo check -p converter-gui
```

Expected: PASS.

- [ ] **Step 4: Commit GUI shell**

```powershell
rtk git add crates/converter-gui
rtk git commit -m "feat: add slint gui shell"
```

## Task 9: Wire GUI State, History, And Monitor Profiles

**Files:**
- Modify: `crates/converter-gui/ui/main.slint`
- Modify: `crates/converter-gui/src/controller.rs`
- Create: `crates/converter-gui/src/models.rs`
- Modify: `crates/converter-gui/Cargo.toml`

- [ ] **Step 1: Add Slint model structs**

Create `crates/converter-gui/src/models.rs`:

```rust
use app_state::{ConversionHistoryItem, MonitorProfile};
use slint::SharedString;

#[derive(Clone, Debug, Default)]
pub struct UiProfile {
    pub id: SharedString,
    pub name: SharedString,
    pub folder: SharedString,
    pub enabled: bool,
}

#[derive(Clone, Debug, Default)]
pub struct UiHistoryItem {
    pub source: SharedString,
    pub output: SharedString,
    pub status: SharedString,
}

impl From<&MonitorProfile> for UiProfile {
    fn from(profile: &MonitorProfile) -> Self {
        Self {
            id: profile.id.clone().into(),
            name: profile.name.clone().into(),
            folder: profile.watch_folder.clone().into(),
            enabled: profile.enabled,
        }
    }
}

impl From<&ConversionHistoryItem> for UiHistoryItem {
    fn from(item: &ConversionHistoryItem) -> Self {
        Self {
            source: item.source_path.clone().into(),
            output: item.output_path.clone().into(),
            status: item.status.clone().into(),
        }
    }
}
```

- [ ] **Step 2: Load persisted settings on startup**

Add to `crates/converter-gui/src/controller.rs`:

```rust
use app_state::{load_profiles_from, profiles_path};

pub fn load_initial_state(app: &AppWindow) {
    if let Ok(path) = profiles_path() {
        if let Ok(doc) = load_profiles_from(path) {
            app.set_remove_backticks(doc.single_file_settings.remove_backticks);
            app.set_auto_detect_dates(doc.single_file_settings.auto_detect_dates);
            app.set_delete_source(doc.single_file_settings.delete_source);
            app.set_output_folder(doc.single_file_settings.last_output_dir.into());
        }
    }
}
```

Modify `crates/converter-gui/src/main.rs`:

```rust
mod controller;
mod models;

slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    let app = AppWindow::new()?;
    controller::load_initial_state(&app);
    controller::wire_callbacks(&app);
    app.run()
}
```

- [ ] **Step 3: Verify GUI compiles**

Run:

```powershell
rtk cargo check -p converter-gui
```

Expected: PASS.

- [ ] **Step 4: Commit GUI state wiring**

```powershell
rtk git add crates/converter-gui
rtk git commit -m "feat: load gui state from appdata"
```

## Task 10: Cut Over Build, Installer, And Docs

**Files:**
- Modify: `build.bat`
- Modify: `.github/workflows/build.yml`
- Modify: `installer.iss`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update local build script**

Replace the PyInstaller build section in `build.bat` with:

```bat
REM Step 1: Build Rust GUI executable
echo [1/2] Building Rust executable...
echo.

cargo build --release -p converter-gui

if errorlevel 1 (
    echo.
    echo ERROR: Cargo build failed
    exit /b 1
)

if not exist "dist" mkdir dist
copy /Y "target\release\csv-xls-converter-gui.exe" "dist\CSV-XLS-Converter.exe"

echo.
echo Rust build complete: dist\CSV-XLS-Converter.exe
echo.
```

- [ ] **Step 2: Update installer source**

In `installer.iss`, ensure the app source line points at:

```ini
Source: "dist\CSV-XLS-Converter.exe"; DestDir: "{app}"; Flags: ignoreversion
```

- [ ] **Step 3: Update README build instructions**

In `README.md`, replace Python build requirements with:

```markdown
### Building Releases

```bash
# Build portable exe only
build.bat

# Build portable exe + Windows installer
build.bat full
```

Requirements:
- Rust stable toolchain
- Inno Setup 6.x for installer builds
- Microsoft Excel for legacy `.xls` conversion at runtime
```
```

- [ ] **Step 4: Verify release build**

Run:

```powershell
rtk cargo build --release -p converter-gui
```

Expected: PASS and `target/release/csv-xls-converter-gui.exe` exists.

- [ ] **Step 5: Commit build cutover**

```powershell
rtk git add build.bat installer.iss README.md CHANGELOG.md .github/workflows/build.yml
rtk git commit -m "build: cut over releases to rust"
```

## Task 11: Full Verification

**Files:**
- No planned file edits.

- [ ] **Step 1: Run all Rust tests**

Run:

```powershell
rtk cargo test --workspace
```

Expected: PASS.

- [ ] **Step 2: Run Rust formatting and linting**

Run:

```powershell
rtk cargo fmt --check
rtk cargo clippy --workspace --all-targets -- -D warnings
```

Expected: PASS.

- [ ] **Step 3: Keep Python tests green during migration**

Run:

```powershell
rtk pytest -q
```

Expected: PASS.

- [ ] **Step 4: Manual smoke test CLI conversion**

Run:

```powershell
rtk pwsh -NoProfile -Command "New-Item -ItemType Directory -Force tmp | Out-Null; Set-Content tmp\sample.csv 'name,value`na,1`nb,NAN'; cargo run -p converter-cli -- tmp\sample.csv -o tmp\sample.xlsx"
```

Expected: command exits `0`, prints a success message, and `tmp/sample.xlsx` exists.

- [ ] **Step 5: Manual smoke test GUI startup**

Run:

```powershell
rtk cargo run -p converter-gui
```

Expected: Slint window opens with Convert, Monitor, History, and Settings tabs.

- [ ] **Step 6: Commit final verification fixes if needed**

If verification revealed small fixes, stage only those files and commit:

```powershell
rtk git add <fixed-files>
rtk git commit -m "fix: complete rust port verification"
```

If no fixes were needed, do not create an empty commit.

## Self-Review

- Spec coverage: The plan covers workspace architecture, conversion behavior, CLI behavior, Slint GUI shell, AppData compatibility, monitor filtering, Windows helper foundations, build cutover, and verification.

- Red-flag scan: No deferred implementation markers are intentionally left in this plan.
- Type consistency: Public Rust names introduced early are reused consistently: `ConvertOptions`, `ConvertError`, `CellValue`, `MonitorProfile`, `ProfileDocument`, `AppWindow`.
