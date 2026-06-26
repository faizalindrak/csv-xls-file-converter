#[test]
fn standard_widgets_use_light_palette_when_window_surface_is_light() {
    // Given a fixed light window background in the Slint UI
    let ui_source = include_str!("../ui/main.slint");

    // When std-widgets are used inside that window
    let uses_standard_widgets = ui_source.contains("\"std-widgets.slint\"");
    let uses_light_window_surface = ui_source.contains("background: Theme.background");

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
    assert!(
        ui_source.contains("border-color: input.has-focus ? Theme.primary : Theme.border-strong")
    );
    assert!(ui_source.contains("component PrimaryButton inherits Rectangle"));
    assert!(ui_source.contains("background: touch.has-hover ? Theme.primary-dark : Theme.primary"));
    assert!(ui_source.contains("color: Theme.card"));
    assert!(ui_source.contains("text: \"Convert to XLSX\";"));
    assert!(ui_source.contains("clicked => { root.convert-file(); }"));

    // And fixed-height controls must not stretch into low-contrast blank panels.
    assert!(ui_source.contains("height: 48px;"));
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

#[test]
fn typography_tokens_raise_contrast_for_utility_surfaces() {
    // Given the desktop utility design system calls for stronger contrast than the default Slint palette
    let ui_source = include_str!("../ui/main.slint");

    // Then the theme tokens should match the design-system contrast targets.
    assert!(ui_source.contains("out property <color> background: #EEF2F7;"));
    assert!(ui_source.contains("out property <color> text-primary: #1B1F24;"));
    assert!(ui_source.contains("out property <color> text-secondary: #4B5563;"));
    assert!(ui_source.contains("out property <color> text-tertiary: #8B95A3;"));
    assert!(ui_source.contains("out property <color> border-strong: #B8C2CF;"));
    assert!(
        ui_source.contains("border-color: input.has-focus ? Theme.primary : Theme.border-strong")
    );
    assert!(ui_source.contains("color: Theme.text-tertiary;"));
}

#[test]
fn convert_screen_keeps_headers_top_aligned_and_controls_roomy() {
    // Given the convert tab should read like a compact Windows control surface instead of a stretched marketing page
    let ui_source = include_str!("../ui/main.slint");

    // Then headers should not consume stretch space and controls should use the roomier 48px rhythm.
    assert!(ui_source.contains("component SectionTitle inherits Text {"));
    assert!(ui_source.contains("component Subtitle inherits Text {"));
    assert!(ui_source.contains("component Label inherits Text {"));
    assert!(ui_source.matches("vertical-stretch: 0;").count() >= 6);
    assert!(ui_source.contains("font-size: 28px;"));
    assert!(ui_source.contains("height: 48px;"));
    assert!(ui_source.matches("padding: Theme.spacing-lg;").count() >= 4);
    assert!(ui_source.matches("spacing: Theme.spacing-lg;").count() >= 3);
}

#[test]
fn monitor_and_history_surfaces_support_editing_scroll_and_unclipped_status_badges() {
    // Given the monitor and history tabs present dense operational data
    let ui_source = include_str!("../ui/main.slint");

    // Then history badges must have enough room for full status labels.
    assert!(ui_source.contains("component StatusBadge inherits Rectangle {"));
    assert!(ui_source.contains("width: 116px;"));
    assert!(ui_source.contains("height: 28px;"));

    // And monitor rows must expose an explicit edit action, not just delete.
    assert!(ui_source.contains("callback edit-profile(string);"));
    assert!(ui_source
        .contains(r#"text: root.editing-profile-id == "" ? "Add Profile" : "Update Profile";"#));
    assert!(ui_source.contains(r#"text: "Edit";"#));

    // And long monitor/history lists should scroll instead of clipping the bottom rows.
    assert!(ui_source.contains(
        r#"import { CheckBox, Palette, ScrollView, TabWidget } from "std-widgets.slint";"#
    ));
    assert!(ui_source.matches("ScrollView {").count() >= 2);

    // And history rows should expose a converted timestamp, not just paths.
    assert!(ui_source.contains("timestamp: string,"));
    assert!(ui_source.contains(r#"text: "Converted";"#));
    assert!(ui_source.contains("text: root.item.timestamp;"));
}
