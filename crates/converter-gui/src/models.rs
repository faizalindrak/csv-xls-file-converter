use std::rc::Rc;

use app_state::{ConversionHistoryItem, MonitorProfile};
use chrono::{DateTime, Local, Utc};
use slint::{ModelRc, SharedString, VecModel};

use crate::{HistoryRow, ProfileRow};

pub fn profile_model(profiles: &[MonitorProfile]) -> ModelRc<ProfileRow> {
    let rows = profiles
        .iter()
        .map(|profile| ProfileRow {
            id: SharedString::from(profile.id.clone()),
            name: SharedString::from(profile.name.clone()),
            folder: SharedString::from(profile.watch_folder.clone()),
            enabled: profile.enabled,
        })
        .collect::<Vec<_>>();
    ModelRc::from(Rc::new(VecModel::from(rows)))
}

pub fn history_model(history: &[ConversionHistoryItem]) -> ModelRc<HistoryRow> {
    let rows = history
        .iter()
        .map(|item| HistoryRow {
            source: SharedString::from(item.source_path.clone()),
            output: SharedString::from(item.output_path.clone()),
            status: SharedString::from(item.status.clone()),
            timestamp: format_history_timestamp(item.timestamp),
            error_message: SharedString::from(item.error_message.clone()),
        })
        .collect::<Vec<_>>();
    ModelRc::from(Rc::new(VecModel::from(rows)))
}

fn format_history_timestamp(timestamp: f64) -> SharedString {
    if !timestamp.is_finite() {
        return SharedString::new();
    }

    let seconds = timestamp.trunc() as i64;
    let nanos = (timestamp.fract().abs() * 1_000_000_000.0).round() as u32;
    let normalized_nanos = nanos.min(999_999_999);

    DateTime::<Utc>::from_timestamp(seconds, normalized_nanos)
        .map(|datetime| {
            datetime
                .with_timezone(&Local)
                .format("%Y-%m-%d %H:%M:%S %Z")
                .to_string()
        })
        .map(SharedString::from)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use chrono::{Local, TimeZone};

    #[test]
    fn format_history_timestamp_converts_unix_seconds_to_local_text() {
        let formatted = super::format_history_timestamp(0.0);
        let expected = Local
            .timestamp_opt(0, 0)
            .single()
            .expect("unix epoch should be representable in local time")
            .format("%Y-%m-%d %H:%M:%S %Z")
            .to_string();

        assert_eq!(formatted.as_str(), expected);
    }

    #[test]
    fn format_history_timestamp_returns_empty_for_invalid_numbers() {
        let formatted = super::format_history_timestamp(f64::NAN);

        assert_eq!(formatted.as_str(), "");
    }
}
