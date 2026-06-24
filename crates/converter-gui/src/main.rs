#![windows_subsystem = "windows"]

mod controller;
mod models;
mod silent;

slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    if let Some(input) = silent::silent_input_from_args(std::env::args_os()) {
        std::process::exit(silent::run_silent_conversion(&input));
    }

    slint::BackendSelector::new()
        .backend_name("winit".into())
        .select()?;

    let app = AppWindow::new()?;
    controller::load_initial_state(&app);
    controller::wire_callbacks(&app);
    app.run()
}
