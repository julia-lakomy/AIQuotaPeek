// KWin sees Wayland windows; ordinary background applications cannot.
const watched = new Set();

function fullscreenVisible() {
    const window = workspace.activeWindow;
    return Boolean(window && window.normalWindow && window.fullScreen && !window.minimized);
}

function report() {
    callDBus("org.limityai.Widget", "/Status", "org.limityai.Widget", "SetFullscreen", fullscreenVisible());
}

function watch(window) {
    if (watched.has(window)) return;
    watched.add(window);
    window.fullScreenChanged.connect(report);
    window.minimizedChanged.connect(report);
    window.desktopsChanged.connect(report);
    window.closed.connect(() => {
        watched.delete(window);
        report();
    });
}

workspace.windowList().forEach(watch);
workspace.windowAdded.connect(window => { watch(window); report(); });
workspace.windowActivated.connect(report);
workspace.currentDesktopChanged.connect(report);
// Re-send after a reader restart, even if no window changes while gaming.
const heartbeat = new QTimer();
heartbeat.interval = 30000;
heartbeat.timeout.connect(report);
heartbeat.start();
report();
