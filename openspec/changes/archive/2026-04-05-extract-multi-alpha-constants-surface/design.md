## Design

The constants used by `state/multi-alpha-ui.js`, `state/config-draft-core.js`, `desktop-shell/config-workspace.js`, and `desktop-shell/app-shell.js` are exported from a dedicated browser-global script under `frontend/assets/js/state/`.

The new module exposes the same symbols on `window/globalThis` so existing non-module scripts continue to work without behavioral change.
