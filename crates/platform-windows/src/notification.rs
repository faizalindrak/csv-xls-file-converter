pub fn show_notification(title: &str, message: &str) -> Result<(), crate::PlatformError> {
    if cfg!(windows) {
        let _ = (title, message);
        Ok(())
    } else {
        Err(crate::PlatformError::Message(
            "Windows notifications are only available on Windows".to_string(),
        ))
    }
}
