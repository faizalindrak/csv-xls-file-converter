use chrono::NaiveDate;
use regex::Regex;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DateFormat {
    Dmy,
    Mdy,
    Iso,
}

pub fn detect_date_format_for_column(values: &[&str]) -> Option<DateFormat> {
    let iso = Regex::new(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$").ok()?;
    let ambiguous = Regex::new(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$").ok()?;
    let mut dmy_score = 0;
    let mut mdy_score = 0;
    let mut iso_count = 0;
    let mut date_count = 0;

    for raw in values {
        let value = raw.trim();
        if value.is_empty() {
            continue;
        }
        if iso.is_match(value) {
            iso_count += 1;
            date_count += 1;
            continue;
        }
        if let Some(caps) = ambiguous.captures(value) {
            let first = caps[1].parse::<u32>().unwrap_or(0);
            let second = caps[2].parse::<u32>().unwrap_or(0);
            date_count += 1;
            if (13..=31).contains(&first) {
                dmy_score += 10;
            } else if (13..=31).contains(&second) {
                mdy_score += 10;
            }
        }
    }

    if date_count == 0 {
        return None;
    }
    if (iso_count as f64) > (date_count as f64 * 0.5) {
        return Some(DateFormat::Iso);
    }
    if dmy_score > mdy_score {
        Some(DateFormat::Dmy)
    } else if mdy_score > dmy_score {
        Some(DateFormat::Mdy)
    } else {
        Some(DateFormat::Dmy)
    }
}

pub fn parse_date_value(value: &str, format: DateFormat) -> Option<NaiveDate> {
    let value = value.trim();
    if value.is_empty() {
        return None;
    }

    match format {
        DateFormat::Iso => parse_iso_date(value),
        DateFormat::Dmy | DateFormat::Mdy => parse_ambiguous_date(value, format),
    }
}

fn parse_iso_date(value: &str) -> Option<NaiveDate> {
    let re = Regex::new(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$").ok()?;
    let caps = re.captures(value)?;
    NaiveDate::from_ymd_opt(
        caps[1].parse().ok()?,
        caps[2].parse().ok()?,
        caps[3].parse().ok()?,
    )
}

fn parse_ambiguous_date(value: &str, format: DateFormat) -> Option<NaiveDate> {
    let re = Regex::new(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$").ok()?;
    let caps = re.captures(value)?;
    let first = caps[1].parse::<u32>().ok()?;
    let second = caps[2].parse::<u32>().ok()?;
    let mut year = caps[3].parse::<i32>().ok()?;
    if year < 100 {
        year = if year < 50 { 2000 + year } else { 1900 + year };
    }
    let (day, month) = match format {
        DateFormat::Dmy => (first, second),
        DateFormat::Mdy => (second, first),
        DateFormat::Iso => return None,
    };
    NaiveDate::from_ymd_opt(year, month, day)
}
