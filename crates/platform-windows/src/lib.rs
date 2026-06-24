mod notification;
mod registry;
mod xls;

pub use notification::show_notification;
pub use registry::{
    context_menu_command, is_auto_startup_enabled, is_context_menu_registered,
    register_context_menu, set_auto_startup, startup_registry_name, unregister_context_menu,
};
pub use xls::{convert_xls_to_xlsx, create_vbs_script, PlatformError};

pub fn is_windows_feature_available() -> bool {
    cfg!(windows)
}
