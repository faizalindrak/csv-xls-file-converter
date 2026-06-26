# Rust Tray Pane Parity Design

Date: 2026-06-26
Project: CSV/XLS Converter
Scope: Restore the Rust GUI tray experience so it matches the previous Python implementation.

## Summary

The current Rust tray implementation restores the main window to the `History`
tab on left-click. The previous Python implementation instead opened a compact
tray popup near the system tray icon, showed a short recent-history list, let
users open successful conversions directly, and kept `Open App` and `Quit`
actions in the popup footer.

This design restores that Python tray behavior in the Rust GUI while keeping the
existing shared history JSON file, full in-app history tab, minimize-to-tray
behavior, and quit guard intact.

## Goals

- Restore exact Python-style tray parity for the Rust GUI.
- Single-click on the tray icon opens a compact popup near the tray icon.
- Double-click on the tray icon opens the full app window.
- The tray popup shows only the most recent 20 history items.
- Successful items in the tray popup open the converted file directly.
- Failed, skipped, and processing items remain visible but are not clickable.
- The popup footer includes `Open App` and `Quit`.
- Opening the full app from the popup lands on the `History` tab.

## Non-Goals

- Changing the persisted history file format.
- Reducing the full in-app history length from its current Rust behavior.
- Reworking monitor lifecycle, minimize-to-tray behavior, or quit semantics.
- Adding tray-specific filtering, search, or extra actions beyond Python parity.

## Current Gap

The Rust code already has:

- Shared history persistence and refresh logic.
- A full-window `History` tab backed by Slint models.
- Tray icon creation, context menu actions, and minimize-to-tray handling.

The missing piece is a dedicated tray popup surface. Current tray left-click and
double-click behavior routes into the main window instead of showing a compact
tray-local history pane.

## UX Behavior

### Tray interactions

- Single left-click: open the tray popup near the tray icon.
- Double left-click: show and focus the full app window on the `History` tab.
- Right-click: keep the existing tray context menu with `Open`, `Hide`, and
  `Quit`.

### Popup layout

The tray popup should mirror the Python behavior:

- Compact frameless popup.
- Fixed compact size close to Python's `320x420`.
- Header title: `Recent Conversions`.
- Scrollable list of recent conversion items.
- Footer with `Open App` and `Quit`.

### History item behavior

- Show only the most recent 20 items in the tray popup.
- Successful rows are clickable and open the converted output path.
- Failed, skipped, and processing rows are non-clickable.
- Clicking a successful row closes the popup after launching the output.

## Architecture

### Recommended approach

Add a dedicated Rust tray popup surface with its own compact history view model.

This is preferred over reusing the main window in a special mode because it
preserves clear separation between:

- full app behavior
- tray-local behavior
- shared history persistence

It also maps directly to how the Python implementation behaved.

### Components

#### 1. `TrayController`

Keep `TrayController` as the native tray boundary responsible for:

- tray event handling
- tray menu actions
- close/minimize guard behavior
- opening and closing the popup
- routing double-click to the main app

#### 2. Tray popup surface

Introduce a dedicated compact popup surface in the Rust GUI layer for:

- rendering tray history rows
- wiring row click events
- exposing `Open App` and `Quit`
- handling popup-specific sizing and visibility

This surface should not replace the main `AppWindow`.

#### 3. History model shaping

Keep the shared history JSON file as the source of truth, then derive:

- the full history model for the main `History` tab
- a 20-item tray history slice for the popup

This avoids duplicated persistence logic and keeps tray data consistent with CLI,
context-menu, and GUI conversions.

#### 4. Native open-file action

Add an explicit controller/native action for opening an output path so the tray
popup can request:

- open converted file

without embedding OS-specific file opening behavior into Slint UI-only code.

## Data Flow

### Conversion updates

Existing conversion flows already append or update history records. That
behavior remains unchanged:

1. A conversion starts or finishes.
2. Rust updates the shared history data.
3. Rust persists the shared JSON history file.
4. Rust refreshes the full app history model.
5. Rust refreshes the tray popup 20-item history model.

### Tray popup data

The tray popup model is always derived from the newest history snapshot:

- newest items first
- maximum 20 items
- includes success, failed, skipped, and processing statuses

The full in-app history continues to use the larger persisted set already used
by the Rust app.

## Positioning

The tray popup should appear near the tray icon whenever possible.

Positioning rules:

- Use tray icon geometry or event position data if available.
- Prefer placing the popup above or adjacent to the tray icon.
- Clamp the popup within the visible work area so it does not render off-screen.
- If exact tray positioning is unavailable on some systems, fall back to a
  sensible bottom-right work-area placement.

This keeps behavior robust across Windows tray variations while still targeting
Python-like placement.

## Error Handling

- If the tray popup cannot be created, the tray icon and tray menu should remain
  functional.
- If opening a converted file fails, the application should remain alive and
  surface a status message in app state.
- Tray popup failures must not break minimize-to-tray or quit behavior.
- Existing tray initialization failures should continue to degrade gracefully by
  reporting a status message instead of crashing.

## Testing

### Automated tests

Add targeted regression coverage for:

- tray history slicing to 20 items
- clickability rules by status
- popup positioning helper clamping and fallback logic
- tray event routing
  - single-click opens popup
  - double-click opens full app history tab

### Manual verification

Verify on Windows:

- single-click opens the compact tray popup
- double-click opens the full app on the `History` tab
- successful tray rows open converted files
- failed, skipped, and processing rows do not open files
- popup footer `Open App` and `Quit` work
- popup remains on-screen when the tray icon is near screen edges
- full app history remains intact beyond the tray popup's 20-item slice

## Implementation Notes

- Keep current shared persistence APIs and avoid creating a second tray-only
  history store.
- Keep current `active-tab-index` support for routing the full app to `History`.
- Do not change the context menu semantics already present in `TrayController`.
- Prefer small helper functions for history slicing, clickability checks, and
  popup placement so these behaviors can be tested without UI-only harnesses.

## Recommendation

Implement a dedicated compact tray popup backed by a tray-specific 20-item view
model derived from the shared history snapshot.

This gives the closest Python parity with the least long-term coupling between
tray UX and the main application window.
