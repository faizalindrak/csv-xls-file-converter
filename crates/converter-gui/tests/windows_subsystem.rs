#[cfg(windows)]
#[test]
fn gui_binary_uses_windows_subsystem() {
    // Given the GUI executable built by Cargo
    let exe = env!("CARGO_BIN_EXE_csv-xls-converter-gui");
    let bytes = std::fs::read(exe).expect("read GUI executable");

    // When Windows inspects the PE optional header
    let subsystem = pe_subsystem(&bytes).expect("read PE subsystem");

    // Then it must be a GUI subsystem binary so double-clicking it does not create a console.
    assert_eq!(
        subsystem, IMAGE_SUBSYSTEM_WINDOWS_GUI,
        "GUI executable should use Windows GUI subsystem, not console subsystem",
    );
}

#[cfg(windows)]
const IMAGE_SUBSYSTEM_WINDOWS_GUI: u16 = 2;

#[cfg(windows)]
fn pe_subsystem(bytes: &[u8]) -> Option<u16> {
    let pe_offset = read_u32(bytes, 0x3c)? as usize;
    let pe_signature = bytes.get(pe_offset..pe_offset + 4)?;
    if pe_signature != b"PE\0\0" {
        return None;
    }

    let optional_header_offset = pe_offset + 24;
    let subsystem_offset = optional_header_offset + 68;
    read_u16(bytes, subsystem_offset)
}

#[cfg(windows)]
fn read_u16(bytes: &[u8], offset: usize) -> Option<u16> {
    let value = bytes.get(offset..offset + 2)?;
    Some(u16::from_le_bytes([value[0], value[1]]))
}

#[cfg(windows)]
fn read_u32(bytes: &[u8], offset: usize) -> Option<u32> {
    let value = bytes.get(offset..offset + 4)?;
    Some(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}
