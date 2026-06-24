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
