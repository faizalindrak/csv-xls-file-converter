#[test]
fn standard_widgets_use_light_palette_when_window_surface_is_light() {
    // Given a fixed light window background in the Slint UI
    let ui_source = include_str!("../ui/main.slint");

    // When std-widgets are used inside that window
    let uses_standard_widgets = ui_source.contains("\"std-widgets.slint\"");
    let uses_light_window_surface = ui_source.contains("background: COLOR_BACKGROUND");

    // Then their palette must be pinned to light so text stays readable on light surfaces.
    assert!(uses_standard_widgets);
    assert!(uses_light_window_surface);
    assert!(
        ui_source.contains("Palette.color-scheme = ColorScheme.light"),
        "Slint standard widgets must use the light palette with the app's light window surface",
    );
}

#[test]
fn convert_screen_uses_high_contrast_fixed_height_controls() {
    // Given the convert screen is a compact Windows utility surface
    let ui_source = include_str!("../ui/main.slint");
    let design_system = include_str!("../../../DESIGN.md");

    // Then its contrast-critical controls must come from declared design tokens.
    assert!(design_system.contains("`--border-strong`"));
    assert!(ui_source.contains("component TextField inherits Rectangle"));
    assert!(ui_source.contains("border-color: input.has-focus ? COLOR_PRIMARY : COLOR_BORDER"));
    assert!(ui_source.contains("component PrimaryButton inherits Rectangle"));
    assert!(ui_source.contains("background: touch.has-hover ? COLOR_PRIMARY_LIGHT : COLOR_PRIMARY"));
    assert!(ui_source.contains("color: COLOR_CARD"));
    assert!(ui_source.contains("PrimaryButton { text: \"Convert to XLSX\""));

    // And fixed-height controls must not stretch into low-contrast blank panels.
    assert!(ui_source.contains("height: 44px;"));
    assert!(ui_source.contains("vertical-stretch: 0;"));
}

#[test]
fn path_fields_expose_browse_actions() {
    // Given the GUI relies on text path fields for conversion and monitoring
    let ui_source = include_str!("../ui/main.slint");

    // Then every file/folder path field should expose a native browse action.
    assert!(ui_source.contains("callback browse-input-file();"));
    assert!(ui_source.contains("callback browse-output-folder();"));
    assert!(ui_source.contains("callback browse-watch-folder();"));
    assert!(ui_source.contains("callback browse-monitor-output-folder();"));
    assert!(ui_source.contains("component SecondaryButton inherits Rectangle"));
    assert!(ui_source.contains("SecondaryButton { text: \"Browse\""));
    assert!(ui_source.contains("browse => { root.browse-input-file(); }"));
    assert!(ui_source.contains("browse => { root.browse-output-folder(); }"));
    assert!(ui_source.contains("browse => { root.browse-watch-folder(); }"));
    assert!(ui_source.contains("browse => { root.browse-monitor-output-folder(); }"));

    // And non-path text fields should stay text-only.
    assert!(ui_source.contains("TextField {"));
    assert!(ui_source.contains("placeholder: \"Profile name\""));
}
