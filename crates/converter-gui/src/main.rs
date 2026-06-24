mod controller;
mod models;

slint::include_modules!();

fn main() -> Result<(), slint::PlatformError> {
    let app = AppWindow::new()?;
    controller::load_initial_state(&app);
    controller::wire_callbacks(&app);
    app.run()
}
