use std::collections::{HashMap, HashSet};
use std::fs::{self, OpenOptions};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use app_state::{
    history_path, load_history_from, load_profiles_from, profiles_path, save_history_to,
    save_profiles_to, ConversionHistoryItem, MonitorProfile,
};
use converter_cli::conversion::convert_file_to_xlsx;
use converter_cli::monitor::{
    discover_existing_files, is_create_or_move, output_path_for, should_process,
};
use converter_core::ConvertOptions;
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use platform_windows::{
    is_auto_startup_enabled, is_context_menu_registered, register_context_menu, set_auto_startup,
    unregister_context_menu,
};
use rfd::FileDialog;
use slint::winit_030::{winit, EventResult, WinitWindowAccessor};
use slint::{ComponentHandle, SharedString, Weak};

use crate::models::{history_model, profile_model};
use crate::AppWindow;

const HISTORY_LIMIT: usize = 200;
const FILE_READY_ATTEMPTS: usize = 30;
const FILE_READY_RETRY_DELAY: Duration = Duration::from_millis(750);

pub fn load_initial_state(app: &AppWindow) {
    if let Ok(path) = profiles_path() {
        if let Ok(doc) = load_profiles_from(path) {
            app.set_remove_backticks(doc.single_file_settings.remove_backticks);
            app.set_auto_detect_dates(doc.single_file_settings.auto_detect_dates);
            app.set_delete_source(doc.single_file_settings.delete_source);
            app.set_output_folder(doc.single_file_settings.last_output_dir.into());
            app.set_auto_startup_enabled(doc.global_settings.auto_startup);
            app.set_context_menu_enabled(doc.global_settings.context_menu);
            app.set_profiles(profile_model(&doc.profiles));
        }
    }
    sync_windows_integration_state(app);
    refresh_history(app);
}

pub fn wire_callbacks(app: &AppWindow) {
    let context = Arc::new(ControllerContext::new(app));
    context.start_enabled_profiles();
    wire_conversion(app, context.clone());
    wire_browse_actions(app);
    wire_file_drop(app, context.clone());
    wire_profiles(app, context.clone());
    wire_settings(app);
}

struct ControllerContext {
    app: Weak<AppWindow>,
    monitor_manager: Arc<MonitorManager>,
}

impl ControllerContext {
    fn new(app: &AppWindow) -> Self {
        Self {
            app: app.as_weak(),
            monitor_manager: Arc::new(MonitorManager::new(app.as_weak())),
        }
    }

    fn start_enabled_profiles(&self) {
        match load_profile_document() {
            Ok(doc) => {
                self.monitor_manager.sync_profiles(&doc.profiles);
                if let Some(app) = self.app.upgrade() {
                    app.set_profiles(profile_model(&doc.profiles));
                }
            }
            Err(error) => self.update_status_message(format!(
                "Failed to load monitoring profiles at startup: {error}"
            )),
        }
    }

    fn update_status_message(&self, message: String) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_status_message(message.into());
        });
    }

    fn persist_profiles<F>(&self, mutate: F) -> Result<Vec<MonitorProfile>, String>
    where
        F: FnOnce(&mut Vec<MonitorProfile>) -> Result<(), String>,
    {
        let path = profiles_path().map_err(|error| error.to_string())?;
        let mut doc = load_profiles_from(path.clone()).map_err(|error| error.to_string())?;
        mutate(&mut doc.profiles)?;
        save_profiles_to(path, &doc).map_err(|error| error.to_string())?;

        if let Some(app) = self.app.upgrade() {
            app.set_profiles(profile_model(&doc.profiles));
        }
        self.monitor_manager.sync_profiles(&doc.profiles);
        Ok(doc.profiles)
    }
}

struct MonitorManager {
    app: Weak<AppWindow>,
    state: Mutex<MonitorManagerState>,
}

struct MonitorManagerState {
    workers: HashMap<String, MonitorWorkerHandle>,
}

struct MonitorWorkerHandle {
    profile_name: String,
    stop: Arc<AtomicBool>,
    thread: Option<thread::JoinHandle<()>>,
}

impl MonitorManager {
    fn new(app: Weak<AppWindow>) -> Self {
        Self {
            app,
            state: Mutex::new(MonitorManagerState {
                workers: HashMap::new(),
            }),
        }
    }

    fn sync_profiles(&self, profiles: &[MonitorProfile]) {
        let desired_ids = profiles
            .iter()
            .filter(|profile| profile.enabled)
            .map(|profile| profile.id.clone())
            .collect::<HashSet<_>>();

        let mut to_stop = Vec::new();
        {
            let state = self.state.lock().expect("monitor manager state lock poisoned");
            for id in state.workers.keys() {
                if !desired_ids.contains(id) {
                    to_stop.push(id.clone());
                }
            }
        }
        for id in to_stop {
            self.stop_worker(&id);
        }

        for profile in profiles.iter().filter(|profile| profile.enabled) {
            let mut state = self.state.lock().expect("monitor manager state lock poisoned");
            if state.workers.contains_key(&profile.id) {
                continue;
            }

            let stop = Arc::new(AtomicBool::new(false));
            let runtime = MonitorRuntime::new(self.app.clone(), profile.clone(), stop.clone());
            let profile_id = profile.id.clone();
            let profile_name = profile.name.clone();
            let thread = thread::spawn(move || runtime.run());

            state.workers.insert(
                profile_id,
                MonitorWorkerHandle {
                    profile_name,
                    stop,
                    thread: Some(thread),
                },
            );
        }
    }

    fn stop_worker(&self, profile_id: &str) {
        let handle = {
            let mut state = self.state.lock().expect("monitor manager state lock poisoned");
            state.workers.remove(profile_id)
        };

        if let Some(mut handle) = handle {
            handle.stop.store(true, Ordering::SeqCst);
            if let Some(thread) = handle.thread.take() {
                let _ = thread.join();
            }
            self.push_status_message(format!("Monitor stopped: {}", handle.profile_name));
        }
    }

    fn shutdown_all(&self) {
        let ids = {
            let state = self.state.lock().expect("monitor manager state lock poisoned");
            state.workers.keys().cloned().collect::<Vec<_>>()
        };
        for id in ids {
            self.stop_worker(&id);
        }
    }

    fn push_status_message(&self, message: String) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_status_message(message.into());
        });
    }
}

impl Drop for MonitorManager {
    fn drop(&mut self) {
        self.shutdown_all();
    }
}

struct MonitorRuntime {
    app: Weak<AppWindow>,
    profile: MonitorProfile,
    stop: Arc<AtomicBool>,
    history: Arc<Mutex<Vec<ConversionHistoryItem>>>,
    last_processed_timestamp: Arc<Mutex<Option<f64>>>,
}

impl MonitorRuntime {
    fn new(app: Weak<AppWindow>, profile: MonitorProfile, stop: Arc<AtomicBool>) -> Self {
        Self {
            app,
            profile,
            stop,
            history: Arc::new(Mutex::new(load_history().unwrap_or_default())),
            last_processed_timestamp: Arc::new(Mutex::new(None)),
        }
    }

    fn run(self) {
        let profile_name = self.profile_label();
        self.push_status_message(format!("Monitor active: {profile_name}"));

        if let Err(error) = self.run_inner() {
            self.push_status_message(format!("Monitor error ({profile_name}): {error}"));
        } else {
            self.push_status_message(format!("Monitor stopped: {profile_name}"));
        }
    }

    fn run_inner(&self) -> Result<(), String> {
        let watch_folder = PathBuf::from(self.profile.watch_folder.trim());
        if !watch_folder.is_dir() {
            return Err(format!("watch folder not found: {}", watch_folder.display()));
        }

        let allowed_formats = normalized_formats(&self.profile.file_formats);
        let output_folder = normalized_output_folder(&self.profile.output_folder);
        let (queue_tx, queue_rx) = mpsc::channel::<PathBuf>();

        if self.profile.process_existing {
            for path in discover_existing_files(
                &watch_folder,
                &allowed_formats,
                &self.profile.exclude_keywords,
            )
            .map_err(|error| error.to_string())?
            {
                if self.stop.load(Ordering::SeqCst) {
                    return Ok(());
                }
                if self.should_queue_existing_file(&path, output_folder.as_deref()) {
                    let _ = queue_tx.send(path);
                }
            }
        }

        let mut watcher = self.build_watcher(queue_tx.clone())?;
        watcher
            .watch(&watch_folder, RecursiveMode::Recursive)
            .map_err(|error| error.to_string())?;

        let mut queued_paths = HashSet::new();
        while !self.stop.load(Ordering::SeqCst) {
            match queue_rx.recv_timeout(Duration::from_millis(250)) {
                Ok(path) => {
                    let queue_key = normalized_path_key(&path);
                    if !queued_paths.insert(queue_key.clone()) {
                        continue;
                    }
                    self.process_queued_file(&path, output_folder.as_deref(), &allowed_formats);
                    queued_paths.remove(&queue_key);
                }
                Err(mpsc::RecvTimeoutError::Timeout) => continue,
                Err(mpsc::RecvTimeoutError::Disconnected) => break,
            }
        }

        Ok(())
    }

    fn build_watcher(&self, queue_tx: mpsc::Sender<PathBuf>) -> Result<RecommendedWatcher, String> {
        let stop = self.stop.clone();
        let allowed_formats = normalized_formats(&self.profile.file_formats);
        let exclude_keywords = self.profile.exclude_keywords.clone();
        let output_folder = normalized_output_folder(&self.profile.output_folder);

        RecommendedWatcher::new(
            move |result| {
                if stop.load(Ordering::SeqCst) {
                    return;
                }

                let Ok(event) = result else {
                    return;
                };

                if !is_create_or_move(&event.kind) {
                    return;
                }

                for path in event.paths {
                    if !path.is_file() {
                        continue;
                    }

                    let path_string = path.to_string_lossy().to_string();
                    if !should_process(&path_string, &allowed_formats, &exclude_keywords) {
                        continue;
                    }

                    if should_skip_existing_output(&path, output_folder.as_deref()) {
                        continue;
                    }

                    let _ = queue_tx.send(path);
                }
            },
            Config::default().with_poll_interval(Duration::from_secs(1)),
        )
        .map_err(|error| error.to_string())
    }

    fn should_queue_existing_file(&self, path: &Path, output_folder: Option<&Path>) -> bool {
        if !path.is_file() {
            return false;
        }
        let path_string = path.to_string_lossy().to_string();
        should_process(
            &path_string,
            &normalized_formats(&self.profile.file_formats),
            &self.profile.exclude_keywords,
        ) && !should_skip_existing_output(path, output_folder)
    }

    fn process_queued_file(&self, source_path: &Path, output_folder: Option<&Path>, allowed_formats: &[String]) {
        if self.stop.load(Ordering::SeqCst) {
            return;
        }

        let source = source_path.to_path_buf();
        let source_string = source.to_string_lossy().to_string();
        if !should_process(&source_string, allowed_formats, &self.profile.exclude_keywords) {
            return;
        }

        if should_skip_existing_output(&source, output_folder) {
            return;
        }

        let output = output_path_for(
            &source.to_string_lossy(),
            output_folder.map(|path| path.to_string_lossy()).as_deref(),
        );

        let processing_index = self.push_history_entry(ConversionHistoryItem {
            source_path: source.display().to_string(),
            output_path: output.display().to_string(),
            status: "processing".to_string(),
            timestamp: current_timestamp(),
            error_message: String::new(),
        });
        self.push_status_message(format!(
            "Processing {} with monitor {}",
            path_display_name(&source),
            self.profile_label()
        ));

        match wait_for_file_ready(&source, &self.stop) {
            Ok(()) => {
                let result = convert_file_to_xlsx(
                    &source,
                    Some(&output),
                    ConvertOptions {
                        remove_backticks: false,
                        auto_detect_dates: self.profile.auto_detect_dates,
                    },
                );

                match result {
                    Ok(_) => {
                        if self.profile.delete_source {
                            if let Err(error) = fs::remove_file(&source) {
                                self.update_history_entry(
                                    processing_index,
                                    "failed",
                                    format!("Converted but failed to delete source: {error}"),
                                );
                                self.push_status_message(format!(
                                    "Monitor error ({}): failed to delete {}",
                                    self.profile_label(),
                                    path_display_name(&source)
                                ));
                                return;
                            }
                        }

                        self.update_last_processed();
                        self.update_history_entry(processing_index, "success", String::new());
                        self.push_status_message(format!(
                            "Converted {} via monitor {}",
                            path_display_name(&source),
                            self.profile_label()
                        ));
                    }
                    Err(error) => {
                        self.update_history_entry(
                            processing_index,
                            "failed",
                            error.to_string(),
                        );
                        self.push_status_message(format!(
                            "Monitor error ({}): failed to convert {}",
                            self.profile_label(),
                            path_display_name(&source)
                        ));
                    }
                }
            }
            Err(error) => {
                self.update_history_entry(processing_index, "failed", error.clone());
                self.push_status_message(format!(
                    "Monitor waiting failed ({}): {}",
                    self.profile_label(),
                    error
                ));
            }
        }
    }

    fn push_history_entry(&self, entry: ConversionHistoryItem) -> usize {
        let (index, snapshot) = {
            let mut history = self.history.lock().expect("history lock poisoned");
            history.insert(0, entry);
            if history.len() > HISTORY_LIMIT {
                history.truncate(HISTORY_LIMIT);
            }
            (0, history.clone())
        };
        self.persist_history_snapshot(snapshot);
        index
    }

    fn update_history_entry(&self, index: usize, status: &str, error_message: String) {
        let snapshot = {
            let mut history = self.history.lock().expect("history lock poisoned");
            if let Some(entry) = history.get_mut(index) {
                entry.status = status.to_string();
                entry.error_message = error_message;
                entry.timestamp = current_timestamp();
            }
            history.clone()
        };
        self.persist_history_snapshot(snapshot);
    }

    fn persist_history_snapshot(&self, snapshot: Vec<ConversionHistoryItem>) {
        if let Ok(path) = history_path() {
            let _ = save_history_to(path, &snapshot);
        }
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_history_items(history_model(&snapshot));
        });
    }

    fn push_status_message(&self, message: String) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_status_message(message.into());
        });
    }

    fn update_last_processed(&self) {
        let mut last_processed = self
            .last_processed_timestamp
            .lock()
            .expect("timestamp lock poisoned");
        *last_processed = Some(current_timestamp());
    }

    fn profile_label(&self) -> String {
        if self.profile.name.trim().is_empty() {
            self.profile.id.clone()
        } else {
            self.profile.name.clone()
        }
    }
}

fn wire_conversion(app: &AppWindow, context: Arc<ControllerContext>) {
    let weak = app.as_weak();
    app.on_convert_file(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let input = PathBuf::from(app.get_input_path().to_string());
        let output_folder = app.get_output_folder().to_string();
        let remove_backticks = app.get_remove_backticks();
        let auto_detect_dates = app.get_auto_detect_dates();
        let delete_source = app.get_delete_source();
        let output = output_path(&input, &output_folder);

        let _ = weak.upgrade_in_event_loop(move |app| {
            app.set_conversion_result("".into());
            app.set_conversion_success(false);
        });

        let weak = app.as_weak();
        app.set_status_message("Converting...".into());

        let context_clone = context.clone();
        thread::spawn(move || {
            let result = convert_file_to_xlsx(
                &input,
                output.as_deref(),
                ConvertOptions {
                    remove_backticks,
                    auto_detect_dates,
                },
            );

            match result {
                Ok(path) => {
                    let (deletion_success, deletion_error_msg) = if delete_source {
                        match std::fs::remove_file(&input) {
                            Ok(_) => (true, String::new()),
                            Err(e) => (false, e.to_string()),
                        }
                    } else {
                        (true, String::new())
                    };
                    
                    append_history_item(ConversionHistoryItem {
                        source_path: input.display().to_string(),
                        output_path: path.display().to_string(),
                        status: if deletion_success {
                            "success".to_string()
                        } else {
                            "failed".to_string()
                        },
                        timestamp: current_timestamp(),
                        error_message: deletion_error_msg.clone(),
                    });
                    
                    if deletion_success {
                        let msg = format!("Converted: {}", path.display());
                        context_clone.update_status_message(msg.clone());
                        let _ = weak.upgrade_in_event_loop(move |app| {
                            app.set_conversion_result(msg.into());
                            app.set_conversion_success(true);
                        });
                    } else {
                        let msg = format!(
                            "Converted (failed to delete original: {})",
                            deletion_error_msg
                        );
                        let _ = weak.upgrade_in_event_loop(move |app| {
                            app.set_status_message(msg.clone().into());
                            app.set_conversion_result(msg.into());
                            app.set_conversion_success(false);
                        });
                    }
                }
                Err(error) => {
                    append_history_item(ConversionHistoryItem {
                        source_path: input.display().to_string(),
                        output_path: output
                            .as_ref()
                            .map(|path| path.display().to_string())
                            .unwrap_or_default(),
                        status: "failed".to_string(),
                        timestamp: current_timestamp(),
                        error_message: error.to_string(),
                    });
                    let msg = format!("Conversion failed: {error}");
                    let _ = weak.upgrade_in_event_loop(move |app| {
                        app.set_status_message(msg.clone().into());
                        app.set_conversion_result(msg.into());
                        app.set_conversion_success(false);
                    });
                }
            };

            let snapshot = load_history().unwrap_or_default();
            let _ = weak.upgrade_in_event_loop(move |app| {
                app.set_history_items(history_model(&snapshot));
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

fn wire_file_drop(app: &AppWindow, context: Arc<ControllerContext>) {
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
            winit::event::WindowEvent::CloseRequested => {
                context.monitor_manager.shutdown_all();
                if let Some(app) = weak.upgrade() {
                    app.set_status_message("Shutting down monitors...".into());
                }
                EventResult::Propagate
            }
            _ => EventResult::Propagate,
        });
}

fn wire_profiles(app: &AppWindow, context: Arc<ControllerContext>) {
    let weak = app.as_weak();
    let context_for_add = context.clone();
    app.on_add_profile(move || {
        let Some(app) = weak.upgrade() else {
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

        let profile_name = profile.name.clone();
        let result = context_for_add.persist_profiles(move |profiles| {
            profiles.push(profile);
            Ok(())
        });

        match result {
            Ok(_) => app.set_status_message(format!("Profile saved: {profile_name}").into()),
            Err(error) => app.set_status_message(format!("Failed to save profile: {error}").into()),
        }
    });

    let weak = app.as_weak();
    let context_for_delete = context.clone();
    app.on_delete_profile(move |id| {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let id = id.to_string();
        let result = context_for_delete.persist_profiles(|profiles| {
            profiles.retain(|profile| profile.id != id);
            Ok(())
        });

        match result {
            Ok(_) => app.set_status_message("Profile deleted".into()),
            Err(error) => {
                app.set_status_message(format!("Failed to delete profile: {error}").into())
            }
        }
    });

    let weak = app.as_weak();
    app.on_toggle_profile(move |id, enabled| {
        let Some(app) = weak.upgrade() else {
            return;
        };
        let id = id.to_string();
        let result = context.persist_profiles(|profiles| {
            if let Some(profile) = profiles.iter_mut().find(|profile| profile.id == id) {
                profile.enabled = enabled;
                return Ok(());
            }
            Err("profile not found".to_string())
        });

        match result {
            Ok(profiles) => {
                let message = profiles
                    .iter()
                    .find(|profile| profile.id == id)
                    .map(|profile| {
                        let state = if enabled { "Active" } else { "Stopped" };
                        format!("Profile {}: {state}", profile.name)
                    })
                    .unwrap_or_else(|| {
                        if enabled {
                            "Profile enabled".to_string()
                        } else {
                            "Profile disabled".to_string()
                        }
                    });
                app.set_status_message(message.into());
            }
            Err(error) => {
                app.set_status_message(format!("Failed to update profile: {error}").into())
            }
        }
    });
}

fn wire_settings(app: &AppWindow) {
    let weak = app.as_weak();
    app.on_save_settings(move || {
        let Some(app) = weak.upgrade() else {
            return;
        };

        app.set_conversion_result("".into());
        let feedback = save_settings(&app);
        app.set_status_message(feedback.clone().into());
        if feedback.starts_with("Failed") {
            app.set_conversion_result(feedback.into());
        }
    });
}

fn save_settings(app: &AppWindow) -> String {
    let Ok(path) = profiles_path() else {
        return "Failed to save settings: could not locate profiles.json".to_string();
    };
    let Ok(mut doc) = load_profiles_from(path.clone()) else {
        return "Failed to save settings: could not load profiles.json".to_string();
    };

    let requested_auto_startup = app.get_auto_startup_enabled();
    let requested_context_menu = app.get_context_menu_enabled();
    let executable_path = match current_executable_string() {
        Ok(path) => path,
        Err(error) => return format!("Failed to save settings: {error}"),
    };

    if let Err(error) = set_auto_startup(requested_auto_startup, &executable_path) {
        sync_windows_integration_state(app);
        return format!("Failed to update Start with Windows: {error}");
    }

    let context_menu_result = if requested_context_menu {
        register_context_menu(&executable_path)
    } else {
        unregister_context_menu()
    };
    if let Err(error) = context_menu_result {
        sync_windows_integration_state(app);
        return format!("Failed to update Explorer context menu: {error}");
    }

    doc.single_file_settings.last_output_dir = app.get_output_folder().to_string();
    doc.single_file_settings.remove_backticks = app.get_remove_backticks();
    doc.single_file_settings.auto_detect_dates = app.get_auto_detect_dates();
    doc.single_file_settings.delete_source = app.get_delete_source();
    doc.global_settings.auto_startup = requested_auto_startup;
    doc.global_settings.context_menu = requested_context_menu;

    if let Err(error) = save_profiles_to(path, &doc) {
        sync_windows_integration_state(app);
        return format!("Failed to save settings: {error}");
    }

    sync_windows_integration_state(app);

    let startup_message = if requested_auto_startup {
        "Start with Windows enabled"
    } else {
        "Start with Windows disabled"
    };
    let context_menu_message = if requested_context_menu {
        "Explorer context menu enabled"
    } else {
        "Explorer context menu disabled"
    };

    format!("{startup_message}; {context_menu_message}")
}

fn sync_windows_integration_state(app: &AppWindow) {
    if let Ok(enabled) = is_auto_startup_enabled() {
        app.set_auto_startup_enabled(enabled);
    }
    if let Ok(enabled) = is_context_menu_registered() {
        app.set_context_menu_enabled(enabled);
    }
}

fn current_executable_string() -> Result<String, String> {
    std::env::current_exe()
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|error| format!("could not resolve current executable path: {error}"))
}

fn refresh_history(app: &AppWindow) {
    if let Ok(path) = history_path() {
        if let Ok(history) = load_history_from(path) {
            app.set_history_items(history_model(&history));
        }
    }
}

fn load_history() -> Result<Vec<ConversionHistoryItem>, String> {
    let path = history_path().map_err(|error| error.to_string())?;
    load_history_from(path).map_err(|error| error.to_string())
}

fn append_history_item(entry: ConversionHistoryItem) {
    let mut history = load_history().unwrap_or_default();
    history.insert(0, entry);
    if history.len() > HISTORY_LIMIT {
        history.truncate(HISTORY_LIMIT);
    }
    if let Ok(path) = history_path() {
        let _ = save_history_to(path, &history);
    }
}

fn load_profile_document() -> Result<app_state::ProfileDocument, String> {
    let path = profiles_path().map_err(|error| error.to_string())?;
    load_profiles_from(path).map_err(|error| error.to_string())
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

fn normalized_formats(formats: &[String]) -> Vec<String> {
    let mut normalized = formats
        .iter()
        .map(|format| format.trim().to_ascii_lowercase())
        .filter(|format| !format.is_empty() && format != "xlsx")
        .collect::<Vec<_>>();
    if normalized.is_empty() {
        normalized.push("csv".to_string());
        normalized.push("xls".to_string());
    }
    normalized
}

fn normalized_output_folder(output_folder: &str) -> Option<PathBuf> {
    let trimmed = output_folder.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(PathBuf::from(trimmed))
    }
}

fn should_skip_existing_output(source_path: &Path, output_folder: Option<&Path>) -> bool {
    let source_extension = source_path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default();
    if source_extension.eq_ignore_ascii_case("xlsx") {
        return true;
    }

    let output = output_path_for(
        &source_path.to_string_lossy(),
        output_folder.map(|path| path.to_string_lossy()).as_deref(),
    );
    output.exists()
}

fn wait_for_file_ready(path: &Path, stop: &AtomicBool) -> Result<(), String> {
    for attempt in 0..FILE_READY_ATTEMPTS {
        if stop.load(Ordering::SeqCst) {
            return Err("monitor stopped before file became ready".to_string());
        }

        if is_file_ready(path) {
            return Ok(());
        }

        if attempt + 1 < FILE_READY_ATTEMPTS {
            thread::sleep(FILE_READY_RETRY_DELAY);
        }
    }

    Err(format!(
        "timed out waiting for write completion: {}",
        path.display()
    ))
}

fn is_file_ready(path: &Path) -> bool {
    if !path.exists() || !path.is_file() {
        return false;
    }

    let metadata_before = match fs::metadata(path) {
        Ok(metadata) => metadata,
        Err(_) => return false,
    };
    let size_before = metadata_before.len();

    if OpenOptions::new().read(true).write(true).open(path).is_err()
        && OpenOptions::new().read(true).open(path).is_err()
    {
        return false;
    }

    thread::sleep(Duration::from_millis(250));

    match fs::metadata(path) {
        Ok(metadata_after) => metadata_after.len() == size_before,
        Err(_) => false,
    }
}

fn normalized_path_key(path: &Path) -> String {
    path.to_string_lossy().to_ascii_lowercase()
}

fn current_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::*;

    #[test]
    fn dropped_single_file_path_accepts_supported_spreadsheet_files() {
        let csv_path = Path::new(r"C:\input\report.CSV");
        let xls_path = Path::new(r"C:\input\legacy.xls");
        let xlsx_path = Path::new(r"C:\input\already.xlsx");

        let csv_drop = dropped_single_file_path(csv_path);
        let xls_drop = dropped_single_file_path(xls_path);
        let xlsx_drop = dropped_single_file_path(xlsx_path);

        assert_eq!(csv_drop.as_deref(), Some(r"C:\input\report.CSV"));
        assert_eq!(xls_drop.as_deref(), Some(r"C:\input\legacy.xls"));
        assert_eq!(xlsx_drop.as_deref(), Some(r"C:\input\already.xlsx"));
    }

    #[test]
    fn dropped_single_file_path_ignores_unsupported_files() {
        let text_path = Path::new(r"C:\input\notes.txt");

        let dropped_path = dropped_single_file_path(text_path);

        assert_eq!(dropped_path, None);
    }

    #[test]
    fn browse_start_directory_prefers_existing_directory_or_parent() {
        let temp_dir = tempfile::tempdir().expect("create temp directory");
        let input_dir = temp_dir.path().join("input");
        std::fs::create_dir(&input_dir).expect("create input directory");
        let input_file = input_dir.join("report.csv");
        std::fs::write(&input_file, "").expect("create input file");

        let directory_start = browse_start_directory(input_dir.to_str().expect("utf-8 path"));
        let file_start = browse_start_directory(input_file.to_str().expect("utf-8 path"));

        assert_eq!(directory_start.as_deref(), Some(input_dir.as_path()));
        assert_eq!(file_start.as_deref(), Some(input_dir.as_path()));
    }

    #[test]
    fn browse_start_directory_ignores_empty_or_missing_paths() {
        let blank_start = browse_start_directory("   ");
        let missing_start = browse_start_directory(r"C:\definitely\missing\report.csv");

        assert_eq!(blank_start, None);
        assert_eq!(missing_start, None);
    }

    #[test]
    fn normalized_formats_skips_xlsx_and_defaults_to_csv_and_xls() {
        assert_eq!(
            normalized_formats(&["XLSX".to_string(), " ".to_string()]),
            vec!["csv".to_string(), "xls".to_string()]
        );
    }

    #[test]
    fn should_skip_existing_output_skips_xlsx_sources() {
        let path = Path::new(r"C:\input\already.xlsx");
        assert!(should_skip_existing_output(path, None));
    }

    #[test]
    fn is_file_ready_requires_existing_file() {
        let temp_dir = tempfile::tempdir().expect("create temp directory");
        let missing = temp_dir.path().join("missing.csv");
        assert!(!is_file_ready(&missing));
    }
}
