const STARTUP_REG_PATH: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
const CONTEXT_MENU_TEXT: &str = "Convert to XLSX";
const CLASSIC_SHELL_EXTENSIONS: [&str; 2] = [
    r"Software\Classes\.csv\shell\ConvertToXLSX",
    r"Software\Classes\.xls\shell\ConvertToXLSX",
];
const MODERN_SHELL_EXTENSIONS: [&str; 2] = [
    r"Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX",
    r"Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX",
];

pub fn context_menu_command(executable_path: &str) -> String {
    format!("\"{executable_path}\" --silent \"%1\"")
}

pub fn startup_registry_name() -> &'static str {
    "CSV-XLS-Converter"
}

#[cfg(windows)]
pub fn set_auto_startup(enable: bool, executable_path: &str) -> Result<(), crate::PlatformError> {
    use winreg::enums::{HKEY_CURRENT_USER, KEY_QUERY_VALUE, KEY_SET_VALUE};
    use winreg::RegKey;

    let current_user = RegKey::predef(HKEY_CURRENT_USER);
    let key = current_user
        .open_subkey_with_flags(STARTUP_REG_PATH, KEY_SET_VALUE | KEY_QUERY_VALUE)
        .map_err(registry_error)?;

    if enable {
        key.set_value(
            startup_registry_name(),
            &quoted_executable_path(executable_path),
        )
        .map_err(registry_error)?;
    } else {
        match key.delete_value(startup_registry_name()) {
            Ok(()) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(registry_error(error)),
        }
    }

    Ok(())
}

#[cfg(not(windows))]
pub fn set_auto_startup(_enable: bool, _executable_path: &str) -> Result<(), crate::PlatformError> {
    Err(crate::PlatformError::Message(
        "Auto-startup registration is only available on Windows".to_string(),
    ))
}

#[cfg(windows)]
pub fn is_auto_startup_enabled() -> Result<bool, crate::PlatformError> {
    use winreg::enums::{HKEY_CURRENT_USER, KEY_QUERY_VALUE};
    use winreg::RegKey;

    let current_user = RegKey::predef(HKEY_CURRENT_USER);
    let key = current_user
        .open_subkey_with_flags(STARTUP_REG_PATH, KEY_QUERY_VALUE)
        .map_err(registry_error)?;

    match key.get_value::<String, _>(startup_registry_name()) {
        Ok(_) => Ok(true),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(registry_error(error)),
    }
}

#[cfg(not(windows))]
pub fn is_auto_startup_enabled() -> Result<bool, crate::PlatformError> {
    Ok(false)
}

#[cfg(windows)]
pub fn register_context_menu(executable_path: &str) -> Result<(), crate::PlatformError> {
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    let current_user = RegKey::predef(HKEY_CURRENT_USER);
    let command = context_menu_command(executable_path);

    for reg_path in all_context_menu_paths() {
        let (key, _) = current_user
            .create_subkey(reg_path)
            .map_err(registry_error)?;
        key.set_value("", &CONTEXT_MENU_TEXT)
            .map_err(registry_error)?;
        key.set_value("Position", &"Top").map_err(registry_error)?;
        key.set_value("Icon", &executable_path)
            .map_err(registry_error)?;

        let (command_key, _) = current_user
            .create_subkey(format!(r"{reg_path}\command"))
            .map_err(registry_error)?;
        command_key
            .set_value("", &command)
            .map_err(registry_error)?;
    }

    Ok(())
}

#[cfg(not(windows))]
pub fn register_context_menu(_executable_path: &str) -> Result<(), crate::PlatformError> {
    Err(crate::PlatformError::Message(
        "Context menu registration is only available on Windows".to_string(),
    ))
}

#[cfg(windows)]
pub fn unregister_context_menu() -> Result<(), crate::PlatformError> {
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    let current_user = RegKey::predef(HKEY_CURRENT_USER);

    for reg_path in all_context_menu_paths() {
        delete_subkey_if_exists(&current_user, &format!(r"{reg_path}\command"))?;
        delete_subkey_if_exists(&current_user, reg_path)?;
    }

    Ok(())
}

#[cfg(not(windows))]
pub fn unregister_context_menu() -> Result<(), crate::PlatformError> {
    Err(crate::PlatformError::Message(
        "Context menu unregistration is only available on Windows".to_string(),
    ))
}

#[cfg(windows)]
pub fn is_context_menu_registered() -> Result<bool, crate::PlatformError> {
    use winreg::enums::{HKEY_CURRENT_USER, KEY_QUERY_VALUE};
    use winreg::RegKey;

    let current_user = RegKey::predef(HKEY_CURRENT_USER);
    for reg_path in all_context_menu_paths() {
        match current_user.open_subkey_with_flags(reg_path, KEY_QUERY_VALUE) {
            Ok(key) => match key.get_value::<String, _>("") {
                Ok(value) if value == CONTEXT_MENU_TEXT => return Ok(true),
                Ok(_) => continue,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
                Err(error) => return Err(registry_error(error)),
            },
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(registry_error(error)),
        }
    }

    Ok(false)
}

#[cfg(not(windows))]
pub fn is_context_menu_registered() -> Result<bool, crate::PlatformError> {
    Ok(false)
}

#[cfg(windows)]
fn delete_subkey_if_exists(key: &winreg::RegKey, path: &str) -> Result<(), crate::PlatformError> {
    match key.delete_subkey(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(registry_error(error)),
    }
}

fn quoted_executable_path(executable_path: &str) -> String {
    format!("\"{executable_path}\"")
}

fn all_context_menu_paths() -> impl Iterator<Item = &'static str> {
    CLASSIC_SHELL_EXTENSIONS
        .iter()
        .chain(MODERN_SHELL_EXTENSIONS.iter())
        .copied()
}

fn registry_error(error: std::io::Error) -> crate::PlatformError {
    crate::PlatformError::Message(format!("Registry operation failed: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_path_is_wrapped_in_quotes() {
        let quoted = quoted_executable_path(r"C:\Program Files\CSV-XLS-Converter.exe");

        assert_eq!(quoted, r#""C:\Program Files\CSV-XLS-Converter.exe""#);
    }

    #[test]
    fn context_menu_targets_csv_and_xls_paths() {
        let paths = all_context_menu_paths().collect::<Vec<_>>();

        assert!(paths
            .iter()
            .any(|path| path.contains(r".csv\shell\ConvertToXLSX")));
        assert!(paths
            .iter()
            .any(|path| path.contains(r".xls\shell\ConvertToXLSX")));
        assert_eq!(paths.len(), 4);
    }
}
