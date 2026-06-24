# CSV/XLS Converter Design System

## 1. Atmosphere & Identity

A quiet Windows utility for repetitive file work. It should feel precise, sturdy, and calm: a compact control room rather than a marketing surface. The signature is task clarity: paths, statuses, and conversion actions stay visually dominant while decoration stays nearly invisible.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
|------|-------|-------|------|-------|
| Surface/primary | `--surface-primary` | `#F7F8FA` | `#111315` | Window background |
| Surface/secondary | `--surface-secondary` | `#FFFFFF` | `#191C1F` | Panels and list rows |
| Surface/elevated | `--surface-elevated` | `#FFFFFF` | `#202428` | Dialogs and popovers |
| Text/primary | `--text-primary` | `#1B1F24` | `#F2F4F7` | Main text |
| Text/secondary | `--text-secondary` | `#5D6673` | `#B4BCC7` | Labels and metadata |
| Text/tertiary | `--text-tertiary` | `#8B95A3` | `#7C8794` | Disabled and hints |
| Border/default | `--border-default` | `#D8DEE6` | `#30363D` | Controls and dividers |
| Border/subtle | `--border-subtle` | `#E8ECF1` | `#252A30` | Soft separators |
| Accent/primary | `--accent-primary` | `#2563EB` | `#5B8DEF` | Primary actions and focus |
| Accent/hover | `--accent-hover` | `#1D4ED8` | `#7AA2F7` | Primary hover |
| Status/success | `--status-success` | `#15803D` | `#4ADE80` | Completed conversions |
| Status/warning | `--status-warning` | `#B45309` | `#FBBF24` | Cautions |
| Status/error | `--status-error` | `#B91C1C` | `#F87171` | Failures |
| Status/info | `--status-info` | `#2563EB` | `#60A5FA` | Informational states |

### Rules

- Accent color is reserved for commands, focus, and active navigation.
- Status colors appear only with status text or indicators.
- No decorative gradients or ornamental backgrounds.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| H1 | 28px | 650 | 1.25 | 0 | Page headers |
| H2 | 22px | 600 | 1.3 | 0 | Panel headers |
| H3 | 18px | 600 | 1.35 | 0 | Row group labels |
| Body | 14px | 400 | 1.5 | 0 | Default UI text |
| Body/sm | 13px | 400 | 1.45 | 0 | Secondary UI text |
| Caption | 12px | 500 | 1.4 | 0 | Metadata and statuses |

### Font Stack

- Primary: `Segoe UI, system-ui, sans-serif`
- Mono: `Cascadia Mono, Consolas, monospace`

### Rules

- Do not use hero-scale type inside the utility UI.
- Path text may use the mono stack when it improves scanning.

## 4. Spacing & Layout

### Base Unit

All spacing derives from 4px.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight icon/label spacing |
| `--space-2` | 8px | Compact row spacing |
| `--space-3` | 12px | Default control spacing |
| `--space-4` | 16px | Panel padding |
| `--space-6` | 24px | Page padding |
| `--space-8` | 32px | Major group separation |

### Grid

- Window content width is fluid, with controls aligned in predictable columns.
- Minimum practical desktop width is 900px.
- Lists use stable row heights to avoid layout shift during status updates.

### Rules

- No nested cards.
- Repeated items may use bordered rows or shallow cards with radius no larger than 8px.

## 5. Components

### Path Picker

- **Structure**: read-only or editable path field plus browse button.
- **States**: default, focus, disabled, invalid.
- **Spacing**: `--space-2` gap between field and button.
- **Accessibility**: browse button names the path it selects.

### Status Row

- **Structure**: status, source path, output path, timestamp.
- **States**: processing, success, failed, skipped.
- **Spacing**: fixed row height, `--space-3` horizontal gap.

## 6. Motion & Interaction

### Timing

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Micro | 100ms | ease-out | Button and checkbox feedback |
| Standard | 180ms | ease-in-out | Tab and panel transitions |

### Rules

- Motion is subtle and functional.
- Every interactive element has hover, active, focus, and disabled states.
- Respect reduced motion where the platform exposes it.

## 7. Depth & Surface

### Strategy

Use borders and tonal shifts. Avoid heavy shadows.

| Type | Value | Usage |
|------|-------|-------|
| Default border | `1px solid var(--border-default)` | Controls and rows |
| Subtle border | `1px solid var(--border-subtle)` | Panel separators |
| Radius | `8px` maximum | Panels, inputs, repeated rows |
