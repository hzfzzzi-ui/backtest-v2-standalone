## Design

The formal host owner remains `desktop-shell/host.js`, but instead of delegating into legacy `init()` as the primary path, it now prefers `initDesktopAppShell()` from a new `desktop-shell/app-shell.js` module.

`app-shell.js` owns:
- top-level page init
- main tab switching
- load hint summary wiring
- bootstrap source resolution and default source bootstrap
- page-level UI event binding
- right-inspector bridge dispatch

`backtest_v2.js` remains temporarily for compat constants still consumed by legacy multi-alpha/UI code. It no longer owns startup or page wiring.
