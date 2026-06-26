#![windows_subsystem = "windows"]

mod controller;
mod models;
mod silent;
mod tray;
mod tray_popup;

slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    if let Some(input) = silent::silent_input_from_args(std::env::args_os()) {
        std::process::exit(silent::run_silent_conversion(&input));
    }

    slint::BackendSelector::new()
        .backend_name("winit".into())
        .select()?;

    let app = AppWindow::new()?;
    let tray = tray::TrayController::new(&app);
    controller::load_initial_state(&app, &tray);
    controller::wire_callbacks(&app, tray.clone());
    app.show()?;
    tray.install_after_window_shown();
    slint::run_event_loop_until_quit()
}
