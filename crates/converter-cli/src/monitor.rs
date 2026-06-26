use std::fs;
use std::path::{Path, PathBuf};
use std::sync::mpsc::channel;
use std::time::Duration;

use crate::conversion::convert_file_to_xlsx;
use converter_core::ConvertOptions;
use notify::{Config, EventKind, RecommendedWatcher, RecursiveMode, Watcher};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MonitorConfig {
    pub folder_path: PathBuf,
    pub output_folder: Option<PathBuf>,
    pub delete_source: bool,
    pub process_existing: bool,
    pub file_formats: Vec<String>,
    pub exclude_keywords: String,
}

pub fn matches_exclude_keyword(file_path: &str, exclude_keywords: &str) -> bool {
    if exclude_keywords.trim().is_empty() {
        return false;
    }

    let filename = Path::new(file_path)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(file_path)
        .to_ascii_lowercase();

    exclude_keywords
        .split(',')
        .map(|keyword| keyword.trim().to_ascii_lowercase())
        .filter(|keyword| !keyword.is_empty())
        .any(|keyword| filename.contains(&keyword))
}

pub fn should_process(file_path: &str, allowed_formats: &[String], exclude_keywords: &str) -> bool {
    let extension = Path::new(file_path)
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();

    allowed_formats
        .iter()
        .any(|allowed| allowed.eq_ignore_ascii_case(&extension))
        && !matches_exclude_keyword(file_path, exclude_keywords)
}

pub fn output_path_for(source_path: &str, output_folder: Option<&str>) -> PathBuf {
    let source = Path::new(source_path);
    let filename = source
        .file_stem()
        .and_then(|stem| stem.to_str())
        .map(|stem| format!("{stem}.xlsx"))
        .unwrap_or_else(|| "output.xlsx".to_string());

    output_folder
        .map(PathBuf::from)
        .unwrap_or_else(|| source.parent().map_or_else(PathBuf::new, Path::to_path_buf))
        .join(filename)
}

pub fn discover_existing_files(
    folder_path: &Path,
    allowed_formats: &[String],
    exclude_keywords: &str,
) -> std::io::Result<Vec<PathBuf>> {
    let mut files = Vec::new();

    fn walk_directory(
        dir: &Path,
        allowed_formats: &[String],
        exclude_keywords: &str,
        files: &mut Vec<PathBuf>,
    ) -> std::io::Result<()> {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_file()
                && should_process(&path.to_string_lossy(), allowed_formats, exclude_keywords)
            {
                files.push(path);
            } else if path.is_dir() {
                walk_directory(&path, allowed_formats, exclude_keywords, files)?;
            }
        }
        Ok(())
    }

    walk_directory(folder_path, allowed_formats, exclude_keywords, &mut files)?;
    files.sort();
    Ok(files)
}

pub fn monitor_folder(config: MonitorConfig) -> Result<(), String> {
    if !config.folder_path.is_dir() {
        return Err(format!(
            "Folder not found: {}",
            config.folder_path.display()
        ));
    }

    if config.process_existing {
        for path in discover_existing_files(
            &config.folder_path,
            &config.file_formats,
            &config.exclude_keywords,
        )
        .map_err(|err| err.to_string())?
        {
            process_file(&path, &config)?;
        }
    }

    let (tx, rx) = channel();
    let mut watcher = RecommendedWatcher::new(
        move |result| {
            let _ = tx.send(result);
        },
        Config::default().with_poll_interval(Duration::from_secs(1)),
    )
    .map_err(|err| err.to_string())?;
    watcher
        .watch(&config.folder_path, RecursiveMode::Recursive)
        .map_err(|err| err.to_string())?;

    println!("Monitoring folder: {}", config.folder_path.display());
    for event in rx {
        let event = event.map_err(|err| err.to_string())?;
        if is_create_or_move(&event.kind) {
            for path in event.paths {
                if path.is_file()
                    && should_process(
                        &path.to_string_lossy(),
                        &config.file_formats,
                        &config.exclude_keywords,
                    )
                {
                    process_file(&path, &config)?;
                }
            }
        }
    }
    Ok(())
}

pub fn is_create_or_move(kind: &EventKind) -> bool {
    matches!(kind, EventKind::Create(_) | EventKind::Modify(_))
}

fn process_file(source_path: &Path, config: &MonitorConfig) -> Result<(), String> {
    let output_folder = config
        .output_folder
        .as_ref()
        .map(|path| path.to_string_lossy().to_string());
    let output_path = output_path_for(&source_path.to_string_lossy(), output_folder.as_deref());
    if output_path.exists() {
        println!("Skipped (already exists): {}", output_path.display());
        return Ok(());
    }

    println!("Converting: {}", source_path.display());
    convert_file_to_xlsx(
        source_path,
        Some(&output_path),
        ConvertOptions {
            remove_backticks: false,
            auto_detect_dates: false,
        },
    )
    .map_err(|err| err.to_string())?;

    if config.delete_source {
        fs::remove_file(source_path).map_err(|err| err.to_string())?;
    }
    println!("Success: {}", output_path.display());
    Ok(())
}
