# DESIGN.md — System Architecture & Design Tokens

## 1. Overview & Aesthetics
The Text2BPMN web interface adheres strictly to a clean, high-precision native application aesthetic inspired by modern macOS and iPadOS productivity tools. It eliminates visual noise, promotional banners, and arbitrary gradients in favor of structural clarity, high typographic contrast, and responsive layout hierarchies.

---

## 2. Design Tokens (`src/styles/tokens.css`)

### 2.1 Surfaces & Canvas
* `--bg`: `#f5f5f7` (macOS default system canvas background)
* `--surface`: `rgba(255, 255, 255, 0.8)` (translucent background for toolbars, floating controls, and navigation elements with `backdrop-blur: 20px`)
* `--surface-solid`: `#ffffff` (opaque white for cards, panels, and canvas containers)
* `--surface-subtle`: `#f0f0f2` (subtle contrast background for dropzones, chips, table rows, and active states)

### 2.2 Text & Typography
* **Font Family**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
* **Typography Floor**: Strictly **≥ 12px** across the entire UI.
* `--text`: `#1d1d1f` (macOS primary label, high contrast ≥ 14:1)
* `--text-secondary-color`: `#6e6e73` (macOS secondary label, WCAG AA ≥ 4.8:1)
* `--text-tertiary`: `#86868b` (macOS tertiary label for auxiliary metadata)

### 2.3 Interactive & Status Accents
* `--accent`: `#0071e3` (Apple system blue)
* `--accent-hover`: `#0077ed`
* `--accent-active`: `#0062c4`
* `--accent-subtle`: `rgba(0, 113, 227, 0.08)`
* `--separator`: `rgba(0, 0, 0, 0.08)` (subtle structural divider)
* `--separator-strong`: `rgba(0, 0, 0, 0.15)`
* `--danger`: `#df1b41` / `--danger-subtle`: `rgba(223, 27, 65, 0.08)`
* `--success`: `#34c759` / `--success-subtle`: `rgba(52, 199, 89, 0.08)`
* `--warning`: `#ff9500` / `--warning-subtle`: `rgba(255, 149, 0, 0.08)`

### 2.4 Elevation & Shadows
* `--shadow-hairline`: `0 1px 2px rgba(0, 0, 0, 0.04), 0 0 0 1px rgba(0, 0, 0, 0.06)`
* `--shadow-card`: `0 2px 8px rgba(0, 0, 0, 0.04), 0 0 0 1px rgba(0, 0, 0, 0.06)`
* `--shadow-popover`: `0 8px 24px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.06)`
* `--shadow-modal`: `0 16px 40px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(0, 0, 0, 0.08)`

### 2.5 Motion & Transitions
* Dynamic layout transitions use springs: `{ type: 'spring', stiffness: 300, damping: 30 }`
* `--ease-default`: `cubic-bezier(0.25, 1, 0.5, 1)`
* `--duration-fast`: `150ms` / `--duration-normal`: `200ms` / `--duration-slow`: `300ms`

---

## 3. Component Inventory

| Component | Path | Description |
|---|---|---|
| **Button** | `src/components/ui/Button.tsx` | Variants: `primary`, `secondary`, `ghost`, `danger`. Sizes: `sm` (28px), `md` (32px), `lg` (36px). Includes loading state. |
| **SegmentedControl** | `src/components/ui/SegmentedControl.tsx` | iOS/macOS sliding pill selector with active indicator animation. Supports badges. |
| **Sheet** | `src/components/ui/Sheet.tsx` | Slide-over panel (440px) with backdrop, escape listener, header, and action footer. |
| **Popover** | `src/components/ui/Popover.tsx` | Lightweight dropdown menu with click-outside detection and aligned shadow. |
| **Toast** | `src/components/ui/Toast.tsx` | Non-intrusive floating error/info notification with optional recovery actions. |
| **Field** | `src/components/ui/Field.tsx` | Form controls (`Input`, `Textarea`, `Select`) with labels, captions, and error states. |
| **Badge** | `src/components/ui/Badge.tsx` | Inline tags with variants (`neutral`, `accent`, `danger`, `success`) and minimum 12px text. |
| **Skeleton** | `src/components/ui/Skeleton.tsx` | Smooth pulsing placeholder elements for diagram load states. |
| **Toolbar** | `src/components/layout/Toolbar.tsx` | 52px top bar containing vendor profile segmented control, template menu, and export actions. |
| **Sidebar** | `src/components/layout/Sidebar.tsx` | Collapsible 320px ↔ 44px rail for file upload, sample picker, and text input. |
| **Inspector** | `src/components/layout/Inspector.tsx` | 360px right rail with tabs for element details, source traceability, and validation issues. |
| **FloatingControls** | `src/components/layout/FloatingControls.tsx` | Diagram status pill (bottom-left) and viewport navigation pill (bottom-right). |
| **EmptyState** | `src/components/layout/EmptyState.tsx` | High-impact drag-and-drop landing state with sample workflow chips. |
| **BpmnViewer** | `src/components/BpmnViewer.tsx` | Wrapped bpmn-js diagram renderer with SVG/PNG/ZIP multi-format export methods. |
