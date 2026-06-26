use platform_windows::{context_menu_command, create_vbs_script};

#[test]
fn vbs_script_uses_excel_save_as_xlsx_format() {
    let script = create_vbs_script();

    assert!(script.contains("CreateObject(\"Excel.Application\")"));
    assert!(script.contains("SaveAs strXLSXFile, 51"));
}

#[test]
fn context_menu_command_uses_silent_mode() {
    let command = context_menu_command("C:\\Program Files\\CSV-XLS-Converter.exe");

    assert!(command.contains("--silent"));
    assert!(command.contains("\"%1\""));
}
