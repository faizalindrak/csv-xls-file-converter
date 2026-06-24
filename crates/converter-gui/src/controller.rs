use std::path::{Path, PathBuf};
use std::thread;

use app_state::{
    history_path, load_history_from, load_profiles_from, profiles_path, save_profiles_to,
    MonitorProfile,
};
use converter_cli::conversion::convert_file_to_xlsx;
use converter_core::ConvertOptions;
use rfd::FileDialog;
use slint::winit_030::{winit, EventResult, WinitWindowAccessor};
use slint::{ComponentHandle, SharedString};

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
    wire_browse_actions(app);
    wire_file_drop(app);
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
            let result = convert_file_to_xlsx(
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

fn wire_browse_actions(app: &AppWindow) {
    let weak = app.as_weak();
    app.on_browse_input_file(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let current_path = app.get_input_path().to_string();
        if let Some(path) = pick_input_file(&current_path) {
            set_input_path_from_file(&app, &path);
        }
    });

    let weak = app.as_weak();
    app.on_browse_output_folder(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let output_folder = app.get_output_folder().to_string();
        let input_path = app.get_input_path().to_string();
        let start_path = if output_folder.trim().is_empty() {
            input_path.as_str()
        } else {
            output_folder.as_str()
        };
        if let Some(path) = pick_folder("Select output folder", start_path) {
            app.set_output_folder(path_to_shared_string(&path));
            app.set_status_message(format!("Output folder: {}", path.display()).into());
        }
    });

    let weak = app.as_weak();
    app.on_browse_watch_folder(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let watch_folder = app.get_watch_folder().to_string();
        if let Some(path) = pick_folder("Select watch folder", &watch_folder) {
            app.set_watch_folder(path_to_shared_string(&path));
            app.set_status_message(format!("Watch folder: {}", path.display()).into());
        }
    });

    let weak = app.as_weak();
    app.on_browse_monitor_output_folder(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let output_folder = app.get_monitor_output_folder().to_string();
        let watch_folder = app.get_watch_folder().to_string();
        let start_path = if output_folder.trim().is_empty() {
            watch_folder.as_str()
        } else {
            output_folder.as_str()
        };
        if let Some(path) = pick_folder("Select monitor output folder", start_path) {
            app.set_monitor_output_folder(path_to_shared_string(&path));
            app.set_status_message(format!("Monitor output folder: {}", path.display()).into());
        }
    });
}

fn pick_input_file(current_path: &str) -> Option<PathBuf> {
    let mut dialog = FileDialog::new()
        .set_title("Select input file")
        .add_filter("Spreadsheet files", &["csv", "xls", "xlsx"])
        .add_filter("CSV", &["csv"])
        .add_filter("Excel", &["xls", "xlsx"]);
    if let Some(directory) = browse_start_directory(current_path) {
        dialog = dialog.set_directory(directory);
    }
    dialog.pick_file()
}

fn pick_folder(title: &str, current_path: &str) -> Option<PathBuf> {
    let mut dialog = FileDialog::new().set_title(title);
    if let Some(directory) = browse_start_directory(current_path) {
        dialog = dialog.set_directory(directory);
    }
    dialog.pick_folder()
}

fn set_input_path_from_file(app: &AppWindow, path: &Path) {
    let Some(input_path) = dropped_single_file_path(path) else {
        app.set_status_message("Unsupported file type. Choose CSV, XLS, or XLSX.".into());
        return;
    };
    app.set_input_path(SharedString::from(input_path.as_str()));
    app.set_status_message(format!("Selected: {}", path_display_name(path)).into());
}

fn wire_file_drop(app: &AppWindow) {
    let weak = app.as_weak();
    app.window()
        .on_winit_window_event(move |_window, event| match event {
            winit::event::WindowEvent::DroppedFile(path) => {
                let Some(input_path) = dropped_single_file_path(path) else {
                    return EventResult::Propagate;
                };
                let Some(app) = weak.upgrade() else {
                    return EventResult::Propagate;
                };
                app.set_input_path(SharedString::from(input_path.as_str()));
                app.set_status_message(format!("Selected: {}", path_display_name(path)).into());
                EventResult::PreventDefault
            }
            _ => EventResult::Propagate,
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

fn path_to_shared_string(path: &Path) -> SharedString {
    SharedString::from(path.to_string_lossy().as_ref())
}

fn path_display_name(path: &Path) -> String {
    path.file_name()
        .and_then(|name| name.to_str())
        .map(str::to_string)
        .unwrap_or_else(|| path.display().to_string())
}

fn dropped_single_file_path(path: &Path) -> Option<String> {
    let extension = path
        .extension()
        .and_then(|extension| extension.to_str())?
        .to_ascii_lowercase();
    match extension.as_str() {
        "csv" | "xls" | "xlsx" => Some(path.to_string_lossy().into_owned()),
        _ => None,
    }
}

fn browse_start_directory(value: &str) -> Option<PathBuf> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    let path = PathBuf::from(trimmed);
    if path.is_dir() {
        return Some(path);
    }
    path.parent()
        .filter(|parent| !parent.as_os_str().is_empty() && parent.is_dir())
        .map(Path::to_path_buf)
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

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::*;

    #[test]
    fn dropped_single_file_path_accepts_supported_spreadsheet_files() {
        // Given supported single-file converter inputs
        let csv_path = Path::new(r"C:\input\report.CSV");
        let xls_path = Path::new(r"C:\input\legacy.xls");
        let xlsx_path = Path::new(r"C:\input\already.xlsx");

        // When each path is handled as an OS file drop
        let csv_drop = dropped_single_file_path(csv_path);
        let xls_drop = dropped_single_file_path(xls_path);
        let xlsx_drop = dropped_single_file_path(xlsx_path);

        // Then the path is accepted for the input field
        assert_eq!(csv_drop.as_deref(), Some(r"C:\input\report.CSV"));
        assert_eq!(xls_drop.as_deref(), Some(r"C:\input\legacy.xls"));
        assert_eq!(xlsx_drop.as_deref(), Some(r"C:\input\already.xlsx"));
    }

    #[test]
    fn dropped_single_file_path_ignores_unsupported_files() {
        // Given a file type the converter does not accept
        let text_path = Path::new(r"C:\input\notes.txt");

        // When it is handled as an OS file drop
        let dropped_path = dropped_single_file_path(text_path);

        // Then the input field should remain unchanged
        assert_eq!(dropped_path, None);
    }

    #[test]
    fn browse_start_directory_prefers_existing_directory_or_parent() {
        // Given an existing folder and a file inside it
        let temp_dir = tempfile::tempdir().expect("create temp directory");
        let input_dir = temp_dir.path().join("input");
        std::fs::create_dir(&input_dir).expect("create input directory");
        let input_file = input_dir.join("report.csv");
        std::fs::write(&input_file, "").expect("create input file");

        // When a browse dialog is opened from either value
        let directory_start = browse_start_directory(input_dir.to_str().expect("utf-8 path"));
        let file_start = browse_start_directory(input_file.to_str().expect("utf-8 path"));

        // Then it starts in the existing directory.
        assert_eq!(directory_start.as_deref(), Some(input_dir.as_path()));
        assert_eq!(file_start.as_deref(), Some(input_dir.as_path()));
    }

    #[test]
    fn browse_start_directory_ignores_empty_or_missing_paths() {
        // Given blank or missing path values
        let blank_start = browse_start_directory("   ");
        let missing_start = browse_start_directory(r"C:\definitely\missing\report.csv");

        // Then the native dialog should use its platform default.
        assert_eq!(blank_start, None);
        assert_eq!(missing_start, None);
    }
}
