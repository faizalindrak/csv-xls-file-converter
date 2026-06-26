use std::cell::RefCell;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};

use slint::winit_030::{EventResult, WinitWindowAccessor};
use slint::{ComponentHandle, Weak};

use app_state::ConversionHistoryItem;

use crate::models::tray_history_model;
use crate::tray_popup::{
    activation_from_tray_event, default_tray_anchor, is_tray_history_row_clickable,
    open_output_path, popup_position_for, route_tray_activation, work_area_for_app, PopupSize,
    TrayAction, TRAY_POPUP_HEIGHT, TRAY_POPUP_WIDTH,
};
use crate::{AppWindow, TrayHistoryWindow};

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
    history_snapshot: Mutex<Vec<ConversionHistoryItem>>,
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
    tray_popup: TrayHistoryWindow,
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
        Arc::new(Self {
            app: app.as_weak(),
            close_guard: Arc::new(CloseGuard::default()),
            quit_handler: Mutex::new(None),
            ready: AtomicBool::new(false),
            history_snapshot: Mutex::new(Vec::new()),
        })
    }

    pub fn install_after_window_shown(self: &Arc<Self>) {
        self.configure_event_handlers();
        self.schedule_install();
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

    pub fn update_history(&self, history: Vec<ConversionHistoryItem>) {
        {
            let mut snapshot = self
                .history_snapshot
                .lock()
                .expect("tray history snapshot lock poisoned");
            *snapshot = history.clone();
        }

        let _ = self.app.upgrade_in_event_loop(move |_| {
            TRAY_UI_STATE.with(|state| {
                if let Some(ui) = state.borrow().as_ref() {
                    ui.tray_popup
                        .set_history_items(tray_history_model(&history));
                }
            });
        });
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

    fn install_tray(self: &Arc<Self>) -> Result<(), String> {
        let menu = tray_icon::menu::Menu::new();
        let show_item = tray_icon::menu::MenuItem::with_id(TRAY_SHOW_ID, "Open", true, None);
        let hide_item = tray_icon::menu::MenuItem::with_id(TRAY_HIDE_ID, "Hide", true, None);
        let quit_item = tray_icon::menu::MenuItem::with_id(TRAY_QUIT_ID, "Quit", true, None);
        let separator = tray_icon::menu::PredefinedMenuItem::separator();
        menu.append_items(&[&show_item, &hide_item, &separator, &quit_item])
            .map_err(|error| error.to_string())?;

        let tray_popup = TrayHistoryWindow::new().map_err(|error| error.to_string())?;
        self.configure_popup_callbacks(&tray_popup);
        self.apply_popup_history(&tray_popup);

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
                tray_popup,
            });
        });

        self.ready.store(true, Ordering::SeqCst);
        Ok(())
    }

    fn configure_popup_callbacks(self: &Arc<Self>, popup: &TrayHistoryWindow) {
        let controller = Arc::downgrade(self);
        popup.on_open_app(move || {
            if let Some(controller) = controller.upgrade() {
                controller.hide_tray_popup();
                controller.show_history_window();
            }
        });

        let controller = Arc::downgrade(self);
        popup.on_quit_app(move || {
            if let Some(controller) = controller.upgrade() {
                controller.hide_tray_popup();
                controller.quit_application();
            }
        });

        let controller = Arc::downgrade(self);
        popup.on_open_output(move |output| {
            if let Some(controller) = controller.upgrade() {
                if !is_tray_history_row_clickable("success", output.as_str()) {
                    return;
                }
                controller.hide_tray_popup();
                if let Err(error) = open_output_path(Path::new(output.as_str())) {
                    controller.push_status_message(error);
                }
            }
        });
    }

    fn handle_tray_event(&self, event: tray_icon::TrayIconEvent) {
        let (activation, anchor) = activation_from_tray_event(&event);
        match route_tray_activation(activation) {
            TrayAction::ShowPopup => {
                let anchor = anchor.unwrap_or_else(default_tray_anchor);
                self.show_tray_popup(anchor);
            }
            TrayAction::ShowMainWindow => self.show_history_window(),
            TrayAction::Ignore => {}
        }
    }

    fn handle_menu_event(&self, event: tray_icon::menu::MenuEvent) {
        if event.id == TRAY_SHOW_ID {
            self.show_history_window();
        } else if event.id == TRAY_HIDE_ID {
            self.hide_window(TRAY_READY_MESSAGE);
        } else if event.id == TRAY_QUIT_ID {
            self.quit_application();
        }
    }

    fn apply_popup_history(&self, popup: &TrayHistoryWindow) {
        let history = self
            .history_snapshot
            .lock()
            .expect("tray history snapshot lock poisoned")
            .clone();
        popup.set_history_items(tray_history_model(&history));
    }

    fn show_tray_popup(&self, anchor: TrayAnchor) {
        let history = self
            .history_snapshot
            .lock()
            .expect("tray history snapshot lock poisoned")
            .clone();
        let _ = self.app.upgrade_in_event_loop(move |app| {
            let work_area = work_area_for_app(&app, anchor);
            let point = popup_position_for(
                anchor,
                work_area,
                PopupSize {
                    width: TRAY_POPUP_WIDTH,
                    height: TRAY_POPUP_HEIGHT,
                },
            );

            TRAY_UI_STATE.with(|state| {
                if let Some(ui) = state.borrow().as_ref() {
                    ui.tray_popup
                        .set_history_items(tray_history_model(&history));
                    ui.tray_popup
                        .window()
                        .set_position(slint::PhysicalPosition::new(point.x, point.y));
                    let _ = ui.tray_popup.show();
                    ui.tray_popup.window().with_winit_window(|window| {
                        window.focus_window();
                    });
                }
            });
        });
    }

    fn hide_tray_popup(&self) {
        let _ = self.app.upgrade_in_event_loop(move |_| {
            TRAY_UI_STATE.with(|state| {
                if let Some(ui) = state.borrow().as_ref() {
                    let _ = ui.tray_popup.hide();
                }
            });
        });
    }

    fn hide_window(&self, status_message: &str) {
        let message = status_message.to_string();
        let _ = self.app.upgrade_in_event_loop(move |app| {
            let _ = app.hide();
            app.set_status_message(message.into());
        });
    }

    fn show_history_window(&self) {
        let _ = self.app.upgrade_in_event_loop(move |app| {
            app.set_active_tab_index(2);
            app.window().set_minimized(false);
            let _ = app.show();
            app.window().with_winit_window(|window| {
                window.focus_window();
            });
            app.set_status_message("History restored from system tray.".into());
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
