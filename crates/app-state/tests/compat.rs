use app_state::{GlobalSettings, MonitorProfile, ProfileDocument, SingleFileSettings};

#[test]
fn loads_existing_profile_json_shape() {
    let raw = r#"{
        "profiles": [{
            "id": "profile-1",
            "name": "Invoices",
            "watch_folder": "C:\\Input",
            "output_folder": "C:\\Output",
            "enabled": true,
            "delete_source": false,
            "process_existing": true,
            "auto_detect_dates": false,
            "file_formats": ["csv"],
            "exclude_keywords": "temp,backup"
        }],
        "single_file_settings": {
            "last_input_dir": "C:\\Docs",
            "last_output_dir": "C:\\Out",
            "remove_backticks": true,
            "auto_detect_dates": true,
            "delete_source": false
        },
        "global_settings": {
            "auto_startup": true,
            "context_menu": true
        },
        "future_field": "ignored"
    }"#;

    let doc: ProfileDocument = serde_json::from_str(raw).expect("profile JSON should parse");

    assert_eq!(doc.profiles[0].name, "Invoices");
    assert_eq!(doc.profiles[0].file_formats, vec!["csv"]);
    assert_eq!(doc.profiles[0].exclude_keywords, "temp,backup");
    assert!(doc.single_file_settings.remove_backticks);
    assert!(doc.global_settings.auto_startup);
    assert!(doc.global_settings.context_menu);
}

#[test]
fn defaults_match_python_models() {
    let profile = MonitorProfile::default();
    let single = SingleFileSettings::default();
    let global = GlobalSettings::default();

    assert_eq!(profile.name, "New Profile");
    assert_eq!(profile.file_formats, vec!["csv", "xls"]);
    assert!(profile.process_existing);
    assert!(!single.delete_source);
    assert!(!global.auto_startup);
    assert!(!global.context_menu);
}
