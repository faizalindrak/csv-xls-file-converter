use std::path::{Path, PathBuf};

use converter_core::{convert_to_xlsx, ConvertError, ConvertOptions};
use platform_windows::{convert_xls_to_xlsx, PlatformError};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConversionBackend {
    Core,
    LegacyXls,
}

#[derive(Debug, thiserror::Error)]
pub enum ConversionError {
    #[error(transparent)]
    Core(#[from] ConvertError),
    #[error(transparent)]
    Platform(#[from] PlatformError),
}

pub fn conversion_backend_for(source_path: &Path) -> ConversionBackend {
    let extension = source_path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default();

    if extension.eq_ignore_ascii_case("xls") {
        ConversionBackend::LegacyXls
    } else {
        ConversionBackend::Core
    }
}

pub fn output_path_for_conversion(source_path: &Path, output_path: Option<&Path>) -> PathBuf {
    output_path
        .map(Path::to_path_buf)
        .unwrap_or_else(|| source_path.with_extension("xlsx"))
}

pub fn convert_file_to_xlsx(
    source_path: &Path,
    output_path: Option<&Path>,
    options: ConvertOptions,
) -> Result<PathBuf, ConversionError> {
    match conversion_backend_for(source_path) {
        ConversionBackend::Core => Ok(convert_to_xlsx(source_path, output_path, options)?),
        ConversionBackend::LegacyXls => {
            let output = output_path_for_conversion(source_path, output_path);
            Ok(convert_xls_to_xlsx(source_path, &output)?)
        }
    }
}
