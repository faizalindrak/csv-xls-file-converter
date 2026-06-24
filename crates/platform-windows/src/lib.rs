mod notification;
mod registry;
mod xls;

pub use notification::show_notification;
pub use registry::{context_menu_command, register_context_menu, startup_registry_name};
pub use xls::{convert_xls_to_xlsx, create_vbs_script, PlatformError};

pub fn is_windows_feature_available() -> bool {
    cfg!(windows)
}
