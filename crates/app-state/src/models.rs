use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
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

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct SingleFileSettings {
    pub last_input_dir: String,
    pub last_output_dir: String,
    pub remove_backticks: bool,
    pub auto_detect_dates: bool,
    pub delete_source: bool,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct GlobalSettings {
    pub auto_startup: bool,
    pub context_menu: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
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

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct ProfileDocument {
    pub profiles: Vec<MonitorProfile>,
    pub single_file_settings: SingleFileSettings,
    pub global_settings: GlobalSettings,
}
