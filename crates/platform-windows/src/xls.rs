use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, thiserror::Error)]
pub enum PlatformError {
    #[error("{0}")]
    Message(String),
    #[error("I/O error for {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
}

pub fn create_vbs_script() -> &'static str {
    r#"
Set objExcel = CreateObject("Excel.Application")
objExcel.Visible = False
objExcel.DisplayAlerts = False
On Error Resume Next
strXLSFile = WScript.Arguments(0)
strXLSXFile = WScript.Arguments(1)
Set objWorkbook = objExcel.Workbooks.Open(strXLSFile)
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to open XLS file: " & Err.Description
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.SaveAs strXLSXFile, 51
If Err.Number <> 0 Then
    WScript.StdErr.WriteLine "Failed to save as XLSX: " & Err.Description
    objWorkbook.Close False
    objExcel.Quit
    WScript.Quit(1)
End If
objWorkbook.Close False
objExcel.Quit
WScript.Quit(0)
"#
}

pub fn convert_xls_to_xlsx(source: &Path, output: &Path) -> Result<PathBuf, PlatformError> {
    if !cfg!(windows) {
        return Err(PlatformError::Message(
            "XLS conversion requires Windows with Microsoft Excel installed".to_string(),
        ));
    }

    let script_path = std::env::temp_dir().join("csv_xls_converter_temp_convert.vbs");
    fs::write(&script_path, create_vbs_script()).map_err(|source| PlatformError::Io {
        path: script_path.clone(),
        source,
    })?;

    let status = Command::new("cscript")
        .arg("//Nologo")
        .arg(&script_path)
        .arg(source)
        .arg(output)
        .status()
        .map_err(|source| PlatformError::Io {
            path: script_path.clone(),
            source,
        })?;
    let _ = fs::remove_file(&script_path);

    if status.success() {
        Ok(output.to_path_buf())
    } else {
        Err(PlatformError::Message("Error converting XLS".to_string()))
    }
}
