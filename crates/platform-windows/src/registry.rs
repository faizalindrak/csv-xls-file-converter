pub fn context_menu_command(executable_path: &str) -> String {
    format!("\"{executable_path}\" --silent \"%1\"")
}

pub fn startup_registry_name() -> &'static str {
    "CSV-XLS-Converter"
}

pub fn register_context_menu(_executable_path: &str) -> Result<(), crate::PlatformError> {
    if cfg!(windows) {
        Ok(())
    } else {
        Err(crate::PlatformError::Message(
            "Context menu registration is only available on Windows".to_string(),
        ))
    }
}
