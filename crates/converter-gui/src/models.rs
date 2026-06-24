use std::rc::Rc;

use app_state::{ConversionHistoryItem, MonitorProfile};
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
        })
        .collect::<Vec<_>>();
    ModelRc::from(Rc::new(VecModel::from(rows)))
}
