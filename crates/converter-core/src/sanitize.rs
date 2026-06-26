pub const EXCEL_MAX_CELL_CHARS: usize = 32_767;
const FORMULA_PREFIXES: [char; 4] = ['=', '+', '-', '@'];

pub fn sanitize_for_xml(value: &str) -> String {
    value
        .chars()
        .filter(|ch| !matches!(*ch as u32, 0x00..=0x08 | 0x0b | 0x0c | 0x0e..=0x1f))
        .collect()
}

pub fn sanitize_for_xlsx_cell(value: &str) -> String {
    let mut sanitized = sanitize_for_xml(value);
    if sanitized
        .chars()
        .next()
        .is_some_and(|ch| FORMULA_PREFIXES.contains(&ch))
    {
        sanitized.insert(0, '\'');
    }
    if sanitized.chars().count() > EXCEL_MAX_CELL_CHARS {
        sanitized = sanitized.chars().take(EXCEL_MAX_CELL_CHARS).collect();
    }
    sanitized
}
