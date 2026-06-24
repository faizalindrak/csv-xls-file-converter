use std::path::PathBuf;

use clap::{CommandFactory, Parser};
use converter_cli::conversion::convert_file_to_xlsx;
use converter_cli::monitor::{monitor_folder, MonitorConfig};
use converter_core::ConvertOptions;
use platform_windows::show_notification;

#[derive(Debug, Parser)]
#[command(
    name = "csv-xls-converter",
    about = "Convert CSV/XLS files to XLSX format with optional folder monitoring."
)]
struct Args {
    input: Option<PathBuf>,
    #[arg(short, long)]
    output: Option<PathBuf>,
    #[arg(long, value_name = "FOLDER")]
    monitor: Option<PathBuf>,
    #[arg(long)]
    delete_source: bool,
    #[arg(long)]
    skip_existing: bool,
    #[arg(long)]
    remove_backticks: bool,
    #[arg(long)]
    silent: bool,
    #[arg(long, value_name = "KEYWORDS")]
    exclude: Option<String>,
}

fn main() {
    let args = Args::parse();
    let code = run(args);
    std::process::exit(code);
}

fn run(args: Args) -> i32 {
    if let Some(folder) = args.monitor {
        let config = MonitorConfig {
            folder_path: folder,
            output_folder: args.output,
            delete_source: args.delete_source,
            process_existing: !args.skip_existing,
            file_formats: vec!["csv".to_string(), "xls".to_string()],
            exclude_keywords: args.exclude.unwrap_or_default(),
        };
        return match monitor_folder(config) {
            Ok(()) => 0,
            Err(error) => {
                if !args.silent {
                    eprintln!("Monitor failed: {error}");
                }
                1
            }
        };
    }

    let Some(input) = args.input else {
        let mut command = Args::command();
        if command.print_help().is_ok() {
            println!();
        }
        return 0;
    };

    if !input.exists() {
        if !args.silent {
            eprintln!("Error: File not found: {}", input.display());
        }
        return 1;
    }

    let result = convert_file_to_xlsx(
        &input,
        args.output.as_deref(),
        ConvertOptions {
            remove_backticks: args.remove_backticks,
            auto_detect_dates: false,
        },
    );

    match result {
        Ok(path) => {
            if args.silent {
                let _ = show_notification(
                    "CSV-XLS Converter",
                    &format!("Converted to {}", path.display()),
                );
            } else {
                println!("Successfully converted to: {}", path.display());
            }
            0
        }
        Err(error) => {
            if args.silent {
                let _ =
                    show_notification("CSV-XLS Converter", &format!("Conversion failed: {error}"));
            } else {
                eprintln!("Conversion failed: {error}");
            }
            1
        }
    }
}
