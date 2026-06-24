use std::fs;
use std::path::PathBuf;

use crate::{ConversionHistoryItem, ProfileDocument};

#[derive(Debug, thiserror::Error)]
pub enum StateError {
    #[error("could not find an application config directory")]
    MissingConfigDir,
    #[error("I/O error for {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("JSON error for {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },
}

pub fn config_dir() -> Result<PathBuf, StateError> {
    let base = dirs::config_dir().ok_or(StateError::MissingConfigDir)?;
    Ok(base.join("csv-xls-converter"))
}

pub fn profiles_path() -> Result<PathBuf, StateError> {
    Ok(config_dir()?.join("profiles.json"))
}

pub fn history_path() -> Result<PathBuf, StateError> {
    Ok(config_dir()?.join("conversion_history.json"))
}

pub fn load_profiles_from(path: PathBuf) -> Result<ProfileDocument, StateError> {
    if !path.exists() {
        return Ok(ProfileDocument::default());
    }

    let text = fs::read_to_string(&path).map_err(|source| StateError::Io {
        path: path.clone(),
        source,
    })?;
    serde_json::from_str(&text).map_err(|source| StateError::Json { path, source })
}

pub fn save_profiles_to(path: PathBuf, doc: &ProfileDocument) -> Result<(), StateError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| StateError::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }

    let text = serde_json::to_string_pretty(doc).map_err(|source| StateError::Json {
        path: path.clone(),
        source,
    })?;
    fs::write(&path, text).map_err(|source| StateError::Io { path, source })
}

pub fn load_history_from(path: PathBuf) -> Result<Vec<ConversionHistoryItem>, StateError> {
    if !path.exists() {
        return Ok(Vec::new());
    }

    let text = fs::read_to_string(&path).map_err(|source| StateError::Io {
        path: path.clone(),
        source,
    })?;
    serde_json::from_str(&text).map_err(|source| StateError::Json { path, source })
}

pub fn save_history_to(
    path: PathBuf,
    history: &[ConversionHistoryItem],
) -> Result<(), StateError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| StateError::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }

    let text = serde_json::to_string_pretty(history).map_err(|source| StateError::Json {
        path: path.clone(),
        source,
    })?;
    fs::write(&path, text).map_err(|source| StateError::Io { path, source })
}
