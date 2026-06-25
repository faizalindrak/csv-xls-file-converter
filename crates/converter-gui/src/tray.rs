use std::cell::RefCell;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};

use slint::winit_030::{EventResult, WinitWindowAccessor};
use slint::{ComponentHandle, Weak};

use crate::AppWindow;

const TRAY_SHOW_ID: &str = "tray.show";
const TRAY_HIDE_ID: &str = "tray.hide";
const TRAY_QUIT_ID: &str = "tray.quit";
const TRAY_TOOLTIP: &str = "CSV/XLS to XLSX Converter";
const TRAY_READY_MESSAGE: &str = "Running in system tray. Monitoring continues in the background.";

thread_local! {
    static TRAY_UI_STATE: RefCell<Option<TrayUiState>> = const { RefCell::new(None) };
}

static TRAY_EVENT_HANDLERS: OnceLock<()> = OnceLock::new();

pub struct TrayController {
    app: Weak<AppWindow>,
    close_guard: Arc<CloseGuard>,
    quit_handler: Mutex<Option<Arc<dyn Fn() + Send + Sync>>>,
    ready: AtomicBool,
}

#[derive(Default)]
pub struct CloseGuard {
    quitting: AtomicBool,
}

struct TrayUiState {
    _menu: tray_icon::menu::Menu,
    _show_item: tray_icon::menu::MenuItem,
    _hide_item: tray_icon::menu::MenuItem,
    _quit_item: tray_icon::menu::MenuItem,
    _tray_icon: tray_icon::TrayIcon,
}

impl CloseGuard {
    pub fn request_quit(&self) {
        self.quitting.store(true, Ordering::SeqCst);
    }

    pub fn should_prevent_close(&self) -> bool {
        !self.quitting.load(Ordering::SeqCst)
    }
}

impl TrayController {
    pub fn new(app: &AppWindow) -> Arc<Self> {
        let controller = Arc::new(Self {
            app: app.as_weak(),
            close_guard: Arc::new(CloseGuard::default()),
            quit_handler: Mutex::new(None),
            ready: AtomicBool::new(false),
        });
        controller.configure_event_handlers();
        controller.schedule_install();
        controller
    }

    pub fn set_quit_handler<F>(&self, handler: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        let mut quit_handler = self
            .quit_handler
            .lock()
            .expect("tray quit handler lock poisoned");
        quit_handler.replace(Arc::new(handler));
    }

    pub fn handle_close_requested(&self) -> EventResult {
        if self.ready.load(Ordering::SeqCst) && self.close_guard.should_prevent_close() {
            self.hide_window(TRAY_READY_MESSAGE);
            return EventResult::PreventDefault;
        }
        EventResult::Propagate
    }

    fn configure_event_handlers(self: &Arc<Self>) {
        let controller = Arc::downgrade(self);
        TRAY_EVENT_HANDLERS.get_or_init(move || {
            let tray_controller = controller.clone();
            tray_icon::TrayIconEvent::set_event_handler(Some(move |event| {
                if let Some(controller) = tray_controller.upgrade() {
                    controller.handle_tray_event(event);
                }
            }));

            tray_icon::menu::MenuEvent::set_event_handler(Some(move |event| {
                if let Some(controller) = controller.upgrade() {
                    controller.handle_menu_event(event);
                }
            }));
        });
    }

    fn schedule_install(self: &Arc<Self>) {
        let controller = Arc::downgrade(self);
        if slint::spawn_local(async move {
            let Some(controller) = controller.upgrade() else {
                return;
            };
            let Some(app) = controller.app.upgrade() else {
                return;
            };

            if app.window().winit_window().await.is_err() {
                controller.push_status_message("System tray could not initialize.".to_string());
                return;
            }

            if let Err(error) = controller.install_tray() {
                controller
                    .push_status_message(format!("System tray could not initialize: {error}"));
            }
        })
        .is_err()
        {
            self.push_status_message("System tray could not initialize.".to_string());
        }
    }

    fn install_tray(&self) -> Result<(), String> {
        let menu = tray_icon::menu::Menu::new();
        let show_item = tray_icon::menu::MenuItem::with_id(TRAY_SHOW_ID, "Open", true, None);
        let hide_item = tray_icon::menu::MenuItem::with_id(TRAY_HIDE_ID, "Hide", true, None);
        let quit_item = tray_icon::menu::MenuItem::with_id(TRAY_QUIT_ID, "Quit", true, None);
        let separator = tray_icon::menu::PredefinedMenuItem::separator();
        menu.append_items(&[&show_item, &hide_item, &separator, &quit_item])
            .map_err(|error| error.to_string())?;

        let tray_icon = tray_icon::TrayIconBuilder::new()
            .with_menu(Box::new(menu.clone()))
            .with_tooltip(TRAY_TOOLTIP)
            .with_menu_on_left_click(false)
            .with_menu_on_right_click(true)
            .with_icon(build_tray_icon()?)
            .build()
            .map_err(|error| error.to_string())?;

        TRAY_UI_STATE.with(|state| {
            state.borrow_mut().replace(TrayUiState {
                _menu: menu,
                _show_item: show_item,
                _hide_item: hide_item,
                _quit_item: quit_item,
                _tray_icon: tray_icon,
            });
        });

        self.ready.store(true, Ordering::SeqCst);
        Ok(())
    }

    fn handle_tray_event(&self, event: tray_icon::TrayIconEvent) {
        use tray_icon::{MouseButton, MouseButtonState, TrayIconEvent};

        match event {
            TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick {
                button: MouseButton::Left,
                ..
            } => self.show_window(),
            _ => {}
        }
    }

    fn handle_menu_event(&self, event: tray_icon::menu::MenuEvent) {
        if event.id == TRAY_SHOW_ID {
            self.show_window();
        } else if event.id == TRAY_HIDE_ID {
            self.hide_window(TRAY_READY_MESSAGE);
        } else if event.id == TRAY_QUIT_ID {
            self.quit_application();
        }
    }

    fn hide_window(&self, status_message: &str) {
        let message = status_message.to_string();
        let _ = self.app.upgrade_in_event_loop(move |app| {
            let _ = app.hide();
            app.set_status_message(message.into());
        });
    }

    fn show_window(&self) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.window().set_minimized(false);
            let _ = app.show();
            app.window().with_winit_window(|window| {
                window.focus_window();
            });
            app.set_status_message("Window restored from system tray.".into());
        });
    }

    fn quit_application(&self) {
        self.close_guard.request_quit();
        if let Some(handler) = self
            .quit_handler
            .lock()
            .expect("tray quit handler lock poisoned")
            .as_ref()
            .cloned()
        {
            handler();
        }
        let _ = self.app.upgrade_in_event_loop(move |app| {
            let _ = app.hide();
        });
        let _ = slint::quit_event_loop();
    }

    fn push_status_message(&self, message: String) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_status_message(message.into());
        });
    }
}

fn build_tray_icon() -> Result<tray_icon::Icon, String> {
    let rgba = tray_icon_rgba();
    tray_icon::Icon::from_rgba(rgba, 16, 16).map_err(|error| error.to_string())
}

fn tray_icon_rgba() -> Vec<u8> {
    let mut rgba = Vec::with_capacity(16 * 16 * 4);
    for y in 0..16 {
        for x in 0..16 {
            let pixel = if !(2..=13).contains(&x) || !(2..=13).contains(&y) {
                [37, 99, 235, 255]
            } else if (4..=11).contains(&x) && (3..=12).contains(&y) {
                [255, 255, 255, 255]
            } else {
                [93, 141, 239, 255]
            };
            rgba.extend_from_slice(&pixel);
        }
    }
    rgba
}

#[cfg(test)]
mod tests {
    use super::{tray_icon_rgba, CloseGuard};

    #[test]
    fn generated_tray_icon_has_expected_rgba_size() {
        let rgba = tray_icon_rgba();

        assert_eq!(rgba.len(), 16 * 16 * 4);
    }

    #[test]
    fn close_guard_allows_quit_after_request() {
        let guard = CloseGuard::default();

        assert!(guard.should_prevent_close());
        guard.request_quit();
        assert!(!guard.should_prevent_close());
    }
}
