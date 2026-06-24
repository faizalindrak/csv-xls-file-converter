use std::ffi::OsString;
use std::path::{Path, PathBuf};

use converter_cli::conversion::convert_file_to_xlsx;
use converter_core::ConvertOptions;
use platform_windows::show_notification;

pub fn silent_input_from_args<I>(args: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = OsString>,
{
    let mut args = args.into_iter();
    let _program = args.next();
    let flag = args.next()?;
    let input = args.next()?;
    if args.next().is_some() || flag != "--silent" {
        return None;
    }
    Some(PathBuf::from(input))
}

pub fn run_silent_conversion(input: &Path) -> i32 {
    if !input.exists() {
        notify(
            "CSV-XLS Converter",
            &format!("File not found: {}", input.display()),
        );
        return 1;
    }

    match convert_file_to_xlsx(
        input,
        None,
        ConvertOptions {
            remove_backticks: false,
            auto_detect_dates: false,
        },
    ) {
        Ok(output) => {
            notify(
                "CSV-XLS Converter",
                &format!("Converted to {}", output.display()),
            );
            0
        }
        Err(error) => {
            notify("CSV-XLS Converter", &format!("Conversion failed: {error}"));
            1
        }
    }
}

fn notify(title: &str, message: &str) {
    let _ = show_notification(title, message);
}

#[cfg(test)]
mod tests {
    use super::silent_input_from_args;
    use std::ffi::OsString;
    use std::path::PathBuf;

    #[test]
    fn detects_silent_context_menu_invocation() {
        let input = silent_input_from_args([
            OsString::from("CSV-XLS-Converter.exe"),
            OsString::from("--silent"),
            OsString::from("C:\\inbox\\report.csv"),
        ]);

        assert_eq!(input, Some(PathBuf::from("C:\\inbox\\report.csv")));
    }

    #[test]
    fn ignores_normal_gui_invocations() {
        let input = silent_input_from_args([OsString::from("CSV-XLS-Converter.exe")]);

        assert_eq!(input, None);
    }
}
