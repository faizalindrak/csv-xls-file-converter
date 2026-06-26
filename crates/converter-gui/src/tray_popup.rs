use std::path::Path;

use slint::winit_030::WinitWindowAccessor;
use slint::ComponentHandle;

use crate::AppWindow;

const POPUP_EDGE_GAP: i32 = 10;
pub(crate) const TRAY_POPUP_WIDTH: i32 = 320;
pub(crate) const TRAY_POPUP_HEIGHT: i32 = 420;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum TrayActivation {
    SingleLeftClick,
    DoubleLeftClick,
    Other,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum TrayAction {
    ShowPopup,
    ShowMainWindow,
    Ignore,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct TrayAnchor {
    pub(crate) x: i32,
    pub(crate) y: i32,
    pub(crate) width: i32,
    pub(crate) height: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct WorkArea {
    pub(crate) x: i32,
    pub(crate) y: i32,
    pub(crate) width: i32,
    pub(crate) height: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct PopupSize {
    pub(crate) width: i32,
    pub(crate) height: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct PopupPoint {
    pub(crate) x: i32,
    pub(crate) y: i32,
}

pub(crate) fn is_tray_history_row_clickable(status: &str, output: &str) -> bool {
    status == "success" && !output.trim().is_empty()
}

pub(crate) fn route_tray_activation(activation: TrayActivation) -> TrayAction {
    match activation {
        TrayActivation::SingleLeftClick => TrayAction::ShowPopup,
        TrayActivation::DoubleLeftClick => TrayAction::ShowMainWindow,
        TrayActivation::Other => TrayAction::Ignore,
    }
}

pub(crate) fn popup_position_for(
    anchor: TrayAnchor,
    work_area: WorkArea,
    popup: PopupSize,
) -> PopupPoint {
    let work_right = work_area.x + work_area.width;
    let work_bottom = work_area.y + work_area.height;
    let centered_x = anchor.x + (anchor.width / 2) - (popup.width / 2);
    let min_x = work_area.x;
    let max_x = (work_right - popup.width).max(min_x);
    let x = centered_x.clamp(min_x, max_x);

    let above_y = anchor.y - popup.height - POPUP_EDGE_GAP;
    let preferred_y = if above_y >= work_area.y {
        above_y
    } else {
        anchor.y + anchor.height + POPUP_EDGE_GAP
    };
    let min_y = work_area.y;
    let max_y = (work_bottom - popup.height).max(min_y);
    let y = preferred_y.clamp(min_y, max_y);

    PopupPoint { x, y }
}

pub(crate) fn activation_from_tray_event(
    event: &tray_icon::TrayIconEvent,
) -> (TrayActivation, Option<TrayAnchor>) {
    use tray_icon::{MouseButton, MouseButtonState, TrayIconEvent};

    match event {
        TrayIconEvent::Click {
            button: MouseButton::Left,
            button_state: MouseButtonState::Up,
            rect,
            ..
        } => (
            TrayActivation::SingleLeftClick,
            Some(anchor_from_rect(*rect)),
        ),
        TrayIconEvent::DoubleClick {
            button: MouseButton::Left,
            rect,
            ..
        } => (
            TrayActivation::DoubleLeftClick,
            Some(anchor_from_rect(*rect)),
        ),
        _ => (TrayActivation::Other, None),
    }
}

fn anchor_from_rect(rect: tray_icon::Rect) -> TrayAnchor {
    TrayAnchor {
        x: rect.position.x.round() as i32,
        y: rect.position.y.round() as i32,
        width: rect.size.width as i32,
        height: rect.size.height as i32,
    }
}

pub(crate) fn default_tray_anchor() -> TrayAnchor {
    TrayAnchor {
        x: 1600,
        y: 900,
        width: 24,
        height: 24,
    }
}

pub(crate) fn work_area_for_app(app: &AppWindow, anchor: TrayAnchor) -> WorkArea {
    app.window()
        .with_winit_window(|window| {
            window
                .current_monitor()
                .map(|monitor| {
                    let position = monitor.position();
                    let size = monitor.size();
                    WorkArea {
                        x: position.x,
                        y: position.y,
                        width: size.width as i32,
                        height: size.height as i32,
                    }
                })
                .unwrap_or_else(|| fallback_work_area(anchor))
        })
        .unwrap_or_else(|| fallback_work_area(anchor))
}

fn fallback_work_area(anchor: TrayAnchor) -> WorkArea {
    WorkArea {
        x: 0,
        y: 0,
        width: (anchor.x + TRAY_POPUP_WIDTH + POPUP_EDGE_GAP).max(1920),
        height: (anchor.y + TRAY_POPUP_HEIGHT + POPUP_EDGE_GAP).max(1080),
    }
}

pub(crate) fn open_output_path(path: &Path) -> Result<(), String> {
    if !path.exists() {
        return Err(format!(
            "Converted file no longer exists: {}",
            path.display()
        ));
    }

    open_existing_output_path(path)
}

#[cfg(target_os = "windows")]
fn open_existing_output_path(path: &Path) -> Result<(), String> {
    std::process::Command::new("rundll32.exe")
        .arg("url.dll,FileProtocolHandler")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("Could not open converted file: {error}"))
}

#[cfg(target_os = "macos")]
fn open_existing_output_path(path: &Path) -> Result<(), String> {
    std::process::Command::new("open")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("Could not open converted file: {error}"))
}

#[cfg(all(unix, not(target_os = "macos")))]
fn open_existing_output_path(path: &Path) -> Result<(), String> {
    std::process::Command::new("xdg-open")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("Could not open converted file: {error}"))
}

#[cfg(not(any(target_os = "windows", target_os = "macos", unix)))]
fn open_existing_output_path(_path: &Path) -> Result<(), String> {
    Err("Opening converted files is not supported on this platform.".to_string())
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;

    use super::{
        is_tray_history_row_clickable, open_output_path, popup_position_for, route_tray_activation,
        PopupPoint, PopupSize, TrayAction, TrayActivation, TrayAnchor, WorkArea,
    };

    #[test]
    fn successful_history_rows_are_clickable() {
        assert!(is_tray_history_row_clickable(
            "success",
            r"C:\out\file.xlsx"
        ));
        assert!(!is_tray_history_row_clickable("success", ""));
        assert!(!is_tray_history_row_clickable(
            "failed",
            r"C:\out\file.xlsx"
        ));
        assert!(!is_tray_history_row_clickable(
            "skipped",
            r"C:\out\file.xlsx"
        ));
        assert!(!is_tray_history_row_clickable(
            "processing",
            r"C:\out\file.xlsx"
        ));
    }

    #[test]
    fn tray_popup_position_prefers_above_tray_and_clamps_to_work_area() {
        let point = popup_position_for(
            TrayAnchor {
                x: 1900,
                y: 1030,
                width: 24,
                height: 24,
            },
            WorkArea {
                x: 0,
                y: 0,
                width: 1920,
                height: 1080,
            },
            PopupSize {
                width: 320,
                height: 420,
            },
        );

        assert_eq!(point, PopupPoint { x: 1600, y: 600 });
    }

    #[test]
    fn tray_popup_position_falls_below_anchor_when_above_would_escape() {
        let point = popup_position_for(
            TrayAnchor {
                x: 12,
                y: 8,
                width: 24,
                height: 24,
            },
            WorkArea {
                x: 0,
                y: 0,
                width: 1024,
                height: 768,
            },
            PopupSize {
                width: 320,
                height: 420,
            },
        );

        assert_eq!(point, PopupPoint { x: 0, y: 42 });
    }

    #[test]
    fn left_single_click_opens_popup_and_double_click_opens_window() {
        assert_eq!(
            route_tray_activation(TrayActivation::SingleLeftClick),
            TrayAction::ShowPopup
        );
        assert_eq!(
            route_tray_activation(TrayActivation::DoubleLeftClick),
            TrayAction::ShowMainWindow
        );
        assert_eq!(
            route_tray_activation(TrayActivation::Other),
            TrayAction::Ignore
        );
    }

    #[test]
    fn opening_missing_output_returns_status_error() {
        let mut missing = PathBuf::from(std::env::temp_dir());
        missing.push("csv-xls-converter-missing-output-for-test.xlsx");

        let error = open_output_path(&missing).expect_err("missing output should not open");

        assert!(error.contains("Converted file no longer exists"));
    }
}
