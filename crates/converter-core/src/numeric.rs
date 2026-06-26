#[derive(Clone, Debug, PartialEq)]
pub enum CellValue {
    Text(String),
    Number(f64),
}

pub fn clean_numeric(input: &str) -> CellValue {
    let s = input.trim();
    if s.is_empty() || s.starts_with('`') {
        return CellValue::Text(s.to_string());
    }
    if s.len() > 1 && s.as_bytes()[0] == b'0' && s.as_bytes()[1].is_ascii_digit() {
        return CellValue::Text(s.to_string());
    }

    let candidates = [
        s.to_string(),
        s.replace(',', "."),
        s.replace('.', "").replace(',', "."),
        s.replace(',', ""),
    ];

    for candidate in candidates {
        if let Ok(number) = candidate.parse::<f64>() {
            if number.is_finite() {
                return CellValue::Number(number);
            }
            return CellValue::Text(s.to_string());
        }
    }

    CellValue::Text(s.to_string())
}
