use std::path::{Path, PathBuf};
use std::thread;

use app_state::{
    history_path, load_history_from, load_profiles_from, profiles_path, save_profiles_to,
    MonitorProfile,
};
use converter_core::{convert_to_xlsx, ConvertOptions};
use slint::ComponentHandle;

use crate::models::{history_model, profile_model};
use crate::AppWindow;

pub fn load_initial_state(app: &AppWindow) {
    if let Ok(path) = profiles_path() {
        if let Ok(doc) = load_profiles_from(path) {
            app.set_remove_backticks(doc.single_file_settings.remove_backticks);
            app.set_auto_detect_dates(doc.single_file_settings.auto_detect_dates);
            app.set_delete_source(doc.single_file_settings.delete_source);
            app.set_output_folder(doc.single_file_settings.last_output_dir.into());
            app.set_profiles(profile_model(&doc.profiles));
        }
    }
    refresh_history(app);
}

pub fn wire_callbacks(app: &AppWindow) {
    wire_conversion(app);
    wire_profiles(app);
}

fn wire_conversion(app: &AppWindow) {
    let weak = app.as_weak();
    app.on_convert_file(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let input = PathBuf::from(app.get_input_path().to_string());
        let output_folder = app.get_output_folder().to_string();
        let remove_backticks = app.get_remove_backticks();
        let auto_detect_dates = app.get_auto_detect_dates();
        let output = output_path(&input, &output_folder);
        let weak = app.as_weak();
        app.set_status_message("Converting...".into());

        thread::spawn(move || {
            let result = convert_to_xlsx(
                &input,
                output.as_deref(),
                ConvertOptions {
                    remove_backticks,
                    auto_detect_dates,
                },
            );
            let message = match result {
                Ok(path) => format!("Converted: {}", path.display()),
                Err(error) => format!("Conversion failed: {error}"),
            };
            let _ = weak.upgrade_in_event_loop(move |app| {
                app.set_status_message(message.into());
            });
        });
    });
}

fn wire_profiles(app: &AppWindow) {
    let weak = app.as_weak();
    app.on_add_profile(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let Ok(path) = profiles_path() else {
            return;
        };
        let Ok(mut doc) = load_profiles_from(path.clone()) else {
            return;
        };
        let mut profile = MonitorProfile {
            name: app.get_profile_name().to_string(),
            watch_folder: app.get_watch_folder().to_string(),
            output_folder: app.get_monitor_output_folder().to_string(),
            process_existing: app.get_process_existing(),
            delete_source: app.get_monitor_delete_source(),
            auto_detect_dates: app.get_monitor_auto_detect_dates(),
            exclude_keywords: app.get_exclude_keywords().to_string(),
            file_formats: selected_formats(
                app.get_monitor_csv_enabled(),
                app.get_monitor_xls_enabled(),
            ),
            ..MonitorProfile::default()
        };
        if profile.name.trim().is_empty() {
            profile.name = "New Profile".to_string();
        }
        doc.profiles.push(profile);
        if save_profiles_to(path, &doc).is_ok() {
            app.set_profiles(profile_model(&doc.profiles));
        }
    });

    let weak = app.as_weak();
    app.on_delete_profile(move |id| {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let Ok(path) = profiles_path() else {
            return;
        };
        let Ok(mut doc) = load_profiles_from(path.clone()) else {
            return;
        };
        let id = id.to_string();
        doc.profiles.retain(|profile| profile.id != id);
        if save_profiles_to(path, &doc).is_ok() {
            app.set_profiles(profile_model(&doc.profiles));
        }
    });

    let weak = app.as_weak();
    app.on_toggle_profile(move |id, enabled| {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let Ok(path) = profiles_path() else {
            return;
        };
        let Ok(mut doc) = load_profiles_from(path.clone()) else {
            return;
        };
        let id = id.to_string();
        if let Some(profile) = doc.profiles.iter_mut().find(|profile| profile.id == id) {
            profile.enabled = enabled;
        }
        if save_profiles_to(path, &doc).is_ok() {
            app.set_profiles(profile_model(&doc.profiles));
        }
    });
}

fn refresh_history(app: &AppWindow) {
    if let Ok(path) = history_path() {
        if let Ok(history) = load_history_from(path) {
            app.set_history_items(history_model(&history));
        }
    }
}

fn output_path(input: &Path, output_folder: &str) -> Option<PathBuf> {
    if output_folder.trim().is_empty() {
        return None;
    }
    let filename = input
        .file_stem()
        .and_then(|stem| stem.to_str())
        .map(|stem| format!("{stem}.xlsx"))
        .unwrap_or_else(|| "output.xlsx".to_string());
    Some(PathBuf::from(output_folder).join(filename))
}

fn selected_formats(csv_enabled: bool, xls_enabled: bool) -> Vec<String> {
    let mut formats = Vec::new();
    if csv_enabled {
        formats.push("csv".to_string());
    }
    if xls_enabled {
        formats.push("xls".to_string());
    }
    if formats.is_empty() {
        formats.push("csv".to_string());
        formats.push("xls".to_string());
    }
    formats
}
