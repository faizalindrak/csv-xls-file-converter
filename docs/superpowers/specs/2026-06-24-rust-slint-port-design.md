# Rust/Slint Port Design

Date: 2026-06-24
Branch: `codex/rust-slint-port`

## Goal

Port CSV/XLS Converter from Python/PySide6 to a full Rust application with a
Slint desktop GUI. The Rust version replaces the existing CLI, GUI, folder
monitor, Windows integrations, and release executable while preserving current
user-facing behavior and existing AppData configuration/history files.

This is a big-bang replacement strategy: Python remains in the repository as a
reference during the port, but the release target becomes the Rust executable
once parity is verified.

## Non-Goals

- Native legacy `.xls` parsing or BIFF conversion.
- Changing the public configuration directory.
- Dropping Windows-specific Excel automation behavior.
- Redesigning the application into a new product workflow.
- Adding unrelated formats beyond the current `.csv`, `.xls`, and `.xlsx`
  behavior.

## Architecture

The Rust application should be organized as a workspace with focused crates:

- `converter-core`: conversion logic, CSV parsing, XLSX writing, sanitization,
  numeric cleanup, date detection, and output path resolution.
- `converter-cli`: command-line entry point matching the current Python CLI.
- `converter-gui`: Slint UI and UI event wiring.
- `app-state`: profile, single-file settings, global settings, and conversion
  history models with JSON persistence.
- `platform-windows`: Windows-only helpers for Excel/VBScript `.xls`
  conversion, Explorer context menu registration, startup registry settings,
  silent notifications, and installer support.

If Cargo workspace overhead becomes noisy during implementation, these crates
may start as modules inside one binary crate, but the code boundaries should
still follow the responsibilities above.

## Conversion Behavior

Single-file conversion must preserve the current behavior:

- `.csv` input is converted to `.xlsx`.
- `.xls` input is converted to `.xlsx` using Windows Script Host and Microsoft
  Excel automation via `cscript` and a generated VBScript.
- `.xlsx` input is copied when the output path differs from the source path.
- Unsupported extensions fail with a clear message.

CSV conversion must preserve these rules:

- Read as UTF-8 first, then fall back to Latin-1-compatible decoding.
- Detect delimiters from a sample and fall back across `;`, `,`, tab, and `|`.
- Treat the first non-empty row as the header.
- Pad ragged rows to the maximum column count.
- Remove illegal XML characters before XLSX writing.
- Escape formula-leading strings that begin with `=`, `+`, `-`, or `@`.
- Trim strings to Excel's 32,767 character cell limit.
- Preserve strings with leading zeroes as text.
- Preserve non-finite tokens such as `NAN`, `INF`, and `-INF` as text.
- Keep backtick-prefixed values as text; when `remove_backticks` is enabled,
  remove the leading backtick and format the column as text.
- When auto date detection is enabled, detect DMY, MDY, and ISO-like date
  columns and write valid dates using the `yyyy-mm-dd` Excel format.

The Rust XLSX writer should be selected during implementation based on support
for string cells, numeric cells, datetime cells, text column formatting, sheet
names, and column widths.

## CLI Behavior

The Rust CLI must match the current `file_converter.py` behavior:

- Positional `input`.
- `-o` / `--output`.
- `--monitor FOLDER`.
- `--delete-source`.
- `--skip-existing`.
- `--remove-backticks`.
- `--silent`.
- `--exclude KEYWORDS`.

Successful conversion exits with code `0`. Failed conversion exits with code
`1`. Silent mode suppresses console output, updates conversion history, and
uses Windows notification support when available.

## GUI Behavior

The Slint GUI must provide the same functional areas as the current PySide6 app:

- Single file conversion with browse controls, drag-and-drop, output folder,
  remove-backticks, auto-date-detection, delete-source, progress, and result
  feedback.
- Monitor profile management with create, edit, delete, enable, disable,
  watch folder, output folder, process-existing, delete-source, auto-dates,
  file format filters, and exclude keywords.
- Recent conversion history with success, failed, skipped, and processing
  states.
- Settings for Windows startup, Explorer context menu registration, and version
  checking.
- System tray behavior where supported by the chosen Rust desktop libraries.

Slint implementation should use external `.slint` files compiled with
`slint-build` from `build.rs`, then included from Rust with
`slint::include_modules!()`. Profile and history lists should use Slint models,
such as `ModelRc<VecModel<...>>`. User actions should flow through Slint
callbacks into Rust application services.

Long-running work must never run on the Slint UI thread. Conversion and folder
monitoring run on worker threads. UI updates are marshaled back to the Slint
event loop with `slint::invoke_from_event_loop` or weak-handle event-loop
upgrades.

## Folder Monitoring

Folder monitoring must preserve:

- Multiple saved monitor profiles.
- Recursive GUI monitoring.
- Existing-file processing when enabled.
- Batch processing and rate limiting.
- Queue size limits to avoid unbounded memory growth.
- CSV/XLS file format filtering per profile.
- Exclude-keyword filtering.
- Skip-if-output-exists behavior.
- Delete-source after successful conversion when enabled.
- Conversion history updates for success, failure, and skipped files.

The Rust implementation should use a filesystem notification crate comparable
to Python `watchdog`. File events should be debounced so partially-written
files are not converted too early.

## Configuration And History Compatibility

The Rust version must continue using the current AppData directory:

- `%APPDATA%/csv-xls-converter/profiles.json`
- `%APPDATA%/csv-xls-converter/conversion_history.json`

Rust data models must deserialize the existing JSON shape:

- `profiles`
- `single_file_settings`
- `global_settings`
- conversion history entries with `source_path`, `output_path`, `status`,
  `timestamp`, and `error_message`

Missing fields should use current defaults. Unknown fields should be ignored
where practical so minor version drift does not break startup.

## Windows Integrations

The Rust replacement must preserve Windows-specific features:

- `.xls` conversion through Excel automation and Windows Script Host.
- Explorer context menu registration under the existing per-user registry
  locations for `.csv` and `.xls`.
- Startup registration under the current user `Run` key.
- Silent-mode notifications.
- Installer support equivalent to the current release process.

Platform-specific functionality should be gated so non-Windows builds can still
compile the CSV-only core and CLI where practical.

## Error Handling

Internally, Rust services should use structured errors with enough detail for
tests and GUI presentation. Externally:

- CLI prints clear failure messages unless `--silent` is active.
- CLI exits with code `1` for failed conversions.
- GUI writes failed conversions into history with the error message.
- Monitor failures are logged per file without crashing the monitor loop.
- Missing optional Windows capabilities produce actionable messages.

## Testing

The port is complete only after Rust tests cover the behavior currently guarded
by Python tests and the important compatibility paths:

- CSV parsing, encoding fallback, and delimiter fallback.
- Numeric cleanup, non-finite token preservation, leading-zero preservation,
  formula escaping, illegal XML character removal, and long-cell trimming.
- Backtick handling and text-column formatting.
- Date detection and date parsing.
- Config and history JSON compatibility.
- CLI arguments, successful exits, and failed exits.
- Monitor format filters, exclude keywords, skip-existing behavior, queue
  behavior, and delete-source behavior.
- Windows helpers through platform-gated tests or explicit smoke checks.

Manual verification should include converting representative `.csv`, `.xls`,
and `.xlsx` files; running folder monitoring; opening the Slint GUI; and
checking the generated executable on Windows.

## Release Cutover

The release cutover should happen only after the Rust executable reaches feature
parity. At that point:

- Build scripts and GitHub Actions should build the Rust executable.
- Installer metadata should use the existing app name and version source.
- Python release packaging can be removed or retained as historical reference,
  but not used as the release artifact.
- Changelog and README should describe the Rust/Slint migration and any
  platform-specific differences.
