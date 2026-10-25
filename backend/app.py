#!/usr/bin/env python3
"""Invisible Qt WebEngine reader and loopback API for the Plasma applet."""

from __future__ import annotations

import copy
import json
import os
import queue
import signal
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import PyQt6

VENDORED_QT = Path(__file__).resolve().parents[1] / ".deps/usr/lib/python3/dist-packages/PyQt6"
if VENDORED_QT.is_dir():
    PyQt6.__path__.append(str(VENDORED_QT))

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, QUrl, QObject, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWidgets import QApplication

from usage_parser import parse_usage


URLS = {
    "chatgpt": "https://chatgpt.com/settings/usage?tab=overview",
    "claude": "https://claude.ai/settings/usage",
}
TIMEZONE = ZoneInfo("Europe/Warsaw")
EMPTY_METRIC = {"remaining": None, "reset": None}


def empty_service() -> dict:
    return {
        "session": dict(EMPTY_METRIC), "weekly": dict(EMPTY_METRIC),
        "lastRead": None, "state": "checking",
    }


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, token: str, state: dict, lock: threading.Lock, actions: queue.Queue):
        super().__init__(address, ApiHandler)
        self.token = token
        self.state = state
        self.lock = lock
        self.actions = actions


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _authorized(self) -> bool:
        return self.headers.get("X-Limity-Token") == self.server.token

    def _reply(self, code: int, value: dict):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._authorized():
            return self._reply(403, {"error": "forbidden"})
        if self.path != "/status":
            return self._reply(404, {"error": "not found"})
        with self.server.lock:
            snapshot = copy.deepcopy(self.server.state)
        self._reply(200, snapshot)

    def do_POST(self):
        if not self._authorized():
            return self._reply(403, {"error": "forbidden"})
        route = urlparse(self.path)
        if route.path == "/refresh":
            action = ("refresh", None)
        elif route.path == "/open":
            service = parse_qs(route.query).get("service", ["all"])[0]
            if service not in (*URLS, "all"):
                return self._reply(400, {"error": "unknown service"})
            action = ("open", service)
        elif route.path == "/finish":
            action = ("finish", None)
        else:
            return self._reply(404, {"error": "not found"})
        self.server.actions.put(action)
        self._reply(202, {"queued": True})


class QuietPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, _level, _message, _line, _source):
        # ChatGPT emits large volumes of diagnostic JS messages while logged out.
        return


class Reader:
    def __init__(self, app: QApplication, config: dict, root: Path):
        self.app = app
        self.root = root
        self.config = config
        self.lock = threading.Lock()
        self.actions: queue.Queue = queue.Queue()
        self.state = {
            "chatgpt": empty_service(), "claude": empty_service(),
            "paused": True, "fullscreenKnown": False,
            "browserOpen": False, "busy": False,
        }
        self.last_fullscreen_report = None
        self.browser: QProcess | None = None
        self.profile: QWebEngineProfile | None = None
        self.page: QWebEnginePage | None = None
        self.current: str | None = None
        self.pending: list[str] = []
        self.attempt = 0
        self.claude_nav_attempted = False
        self.generation = 0
        self.override_pause = False
        self._create_profile()

        self.api = ApiServer(("127.0.0.1", int(config["port"])), config["token"], self.state, self.lock, self.actions)
        threading.Thread(target=self.api.serve_forever, name="widget-api", daemon=True).start()
        self.action_timer = QTimer()
        self.action_timer.timeout.connect(self._drain_actions)
        self.action_timer.start(100)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(5 * 60 * 1000)
        self.fullscreen_watchdog = QTimer()
        self.fullscreen_watchdog.timeout.connect(self._check_fullscreen_report)
        self.fullscreen_watchdog.start(15 * 1000)
        QTimer.singleShot(1500, self.refresh)

    def _set(self, **values):
        with self.lock:
            self.state.update(values)

    def _set_service(self, service: str, **values):
        with self.lock:
            self.state[service].update(values)

    def _create_profile(self):
        profile_dir = self.root / "browser-config/falkon/profiles/limity-ai-widget"
        cache_dir = self.root / "browser-cache/qt"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.profile = QWebEngineProfile("limity-ai-widget", self.app)
        self.profile.setPersistentStoragePath(str(profile_dir))
        self.profile.setCachePath(str(cache_dir))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.page = QuietPage(self.profile, self.app)
        self.page.loadFinished.connect(self._loaded)
        self.page.setVisible(False)

    def _destroy_profile(self):
        self.generation += 1
        self.current = None
        self.pending.clear()
        if self.page:
            self.page.triggerAction(QWebEnginePage.WebAction.Stop)
            self.page.deleteLater()
            self.page = None
        if self.profile:
            self.profile.deleteLater()
            self.profile = None
        self._set(busy=False)

    def _drain_actions(self):
        while not self.actions.empty():
            name, argument = self.actions.get_nowait()
            if name == "refresh":
                self.refresh(manual=True)
            elif name == "open":
                self.open_browser(argument)
            elif name == "finish":
                self.finish_browser()

    def set_fullscreen(self, value: bool):
        value = bool(value)
        self.last_fullscreen_report = time.monotonic()
        was_known = self.state["fullscreenKnown"]
        if was_known and self.state["paused"] == value:
            return
        self._set(paused=value, fullscreenKnown=True)
        if value:
            self.generation += 1
            self.current = None
            self.pending.clear()
            self.override_pause = False
            if self.page:
                self.page.triggerAction(QWebEnginePage.WebAction.Stop)
                self.page.setUrl(QUrl("about:blank"))
            self._set(busy=False)
        else:
            # Avoid loading pages after a brief Alt-Tab away from a game.
            QTimer.singleShot(15 * 1000, self.refresh)

    def _check_fullscreen_report(self):
        if self.last_fullscreen_report is None or time.monotonic() - self.last_fullscreen_report <= 90:
            return
        self.last_fullscreen_report = None
        self._set(paused=True, fullscreenKnown=False, busy=False)
        self.generation += 1
        self.current = None
        self.pending.clear()
        self.override_pause = False
        if self.page:
            self.page.triggerAction(QWebEnginePage.WebAction.Stop)
            self.page.setUrl(QUrl("about:blank"))

    def refresh(self, manual: bool = False):
        if self.browser is not None or self.page is None:
            return
        if (self.state["paused"] or not self.state["fullscreenKnown"]) and not manual:
            return
        if self.current:
            return
        self.override_pause = manual
        self.pending = list(URLS)
        self._set(busy=True)
        self._next()

    def _next(self):
        if (self.state["paused"] and not self.override_pause) or self.browser is not None or self.page is None:
            self.current = None
            self.pending.clear()
            self._set(busy=False)
            return
        if not self.pending:
            self.current = None
            self.override_pause = False
            self._set(busy=False)
            self.page.setUrl(QUrl("about:blank"))
            QTimer.singleShot(700, self._discard_page)
            return
        self.current = self.pending.pop(0)
        self.attempt = 0
        self.claude_nav_attempted = False
        self.generation += 1
        self.page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
        self.page.load(QUrl(URLS[self.current]))

    def _discard_page(self):
        if self.page and not self.current and not self.browser:
            self.page.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)

    def _loaded(self, ok: bool):
        if not self.current:
            return
        generation = self.generation
        if not ok:
            self._finish_current("unavailable")
            return
        QTimer.singleShot(1800, lambda: self._capture(generation))

    def _capture(self, generation: int):
        if generation != self.generation or not self.current or not self.page:
            return
        js = "({url: location.href, text: document.body ? document.body.innerText : ''})"
        self.page.runJavaScript(js, lambda data: self._read_result(generation, data))

    def _read_result(self, generation: int, data):
        if generation != self.generation or not self.current:
            return
        service = self.current
        url = str((data or {}).get("url", ""))
        page_text = str((data or {}).get("text", ""))
        parsed = parse_usage(service, page_text, datetime.now(TIMEZONE))
        parsed_url = urlparse(url)
        has_value = any(parsed[key]["remaining"] is not None for key in ("session", "weekly"))
        if has_value:
            self._set_service(service, **parsed, lastRead=datetime.now(TIMEZONE).isoformat(timespec="minutes"), state="ready")
            self._next()
            return
        if service == "claude" and parsed_url.hostname == "claude.ai" and parsed_url.path == "/new" and not self.claude_nav_attempted:
            self.claude_nav_attempted = True
            click_usage = """(() => {
                const button = Array.from(document.querySelectorAll('button, [role=button]'))
                    .find(el => /usage/i.test((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')));
                if (!button) return false;
                button.click();
                return true;
            })()"""
            self.page.runJavaScript(click_usage, lambda clicked: self._after_claude_nav(generation, clicked))
            return
        lowered = page_text.casefold()
        login_url = parsed_url.hostname not in ("chatgpt.com", "claude.ai") or parsed_url.path.startswith(("/login", "/auth"))
        login_text = any(word in lowered for word in ("log in", "sign in", "zaloguj", "continue with google"))
        if login_url or login_text:
            self._finish_current("login")
        elif self.attempt < 6:
            self.attempt += 1
            QTimer.singleShot(1700, lambda: self._capture(generation))
        else:
            self._finish_current("unavailable")

    def _after_claude_nav(self, generation: int, clicked: bool):
        if generation != self.generation or not self.current:
            return
        QTimer.singleShot(2200, lambda: self._capture(generation))

    def _finish_current(self, state: str):
        if self.current:
            service = self.current
            self._set_service(service, session=dict(EMPTY_METRIC), weekly=dict(EMPTY_METRIC), lastRead=None, state=state)
        self._next()

    def open_browser(self, service: str = "all"):
        if self.browser is not None:
            return
        self._destroy_profile()
        self._set(browserOpen=True)
        QTimer.singleShot(500, lambda: self._launch_browser(service))

    def _launch_browser(self, service: str):
        browser = QProcess(self.app)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("XDG_CONFIG_HOME", str(self.root / "browser-config"))
        env.insert("XDG_DATA_HOME", str(self.root / "browser-data"))
        env.insert("XDG_CACHE_HOME", str(self.root / "browser-cache"))
        env.remove("QT_QPA_PLATFORM")
        browser.setProcessEnvironment(env)
        browser.setProgram("/usr/bin/falkon")
        urls = list(URLS.values()) if service == "all" else [URLS[service]]
        browser.setArguments(["--no-remote", "--profile", "limity-ai-widget", *urls])
        browser.finished.connect(self._browser_closed)
        browser.errorOccurred.connect(self._browser_error)
        self.browser = browser
        browser.start()

    def _browser_error(self, _error):
        if self.browser and self.browser.state() == QProcess.ProcessState.NotRunning:
            self._browser_closed()

    def finish_browser(self):
        """Close all windows of the dedicated Falkon on explicit request."""
        if self.browser is None or self.browser.state() == QProcess.ProcessState.NotRunning:
            return
        pid = int(self.browser.processId())
        if pid <= 0:
            return
        script = self.root / f"close-browser-{pid}.js"
        plugin = f"limity_ai_close_{pid}"
        script.write_text(
            "workspace.windowList().filter(window => window.pid === "
            + str(pid)
            + " && window.closeable).forEach(window => window.closeWindow());\n"
        )
        script.chmod(0o600)
        scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", QDBusConnection.sessionBus())
        if not scripting.isValid():
            script.unlink(missing_ok=True)
            return
        scripting.call("unloadScript", plugin)
        loaded = scripting.call("loadScript", str(script), plugin)
        if loaded.type() == QDBusMessage.MessageType.ErrorMessage:
            script.unlink(missing_ok=True)
            return
        scripting.call("start")
        QTimer.singleShot(3000, lambda: self._cleanup_close_script(plugin, script))

    def _cleanup_close_script(self, plugin: str, script: Path):
        scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", QDBusConnection.sessionBus())
        if scripting.isValid():
            scripting.call("unloadScript", plugin)
        script.unlink(missing_ok=True)

    def _browser_closed(self, *_args):
        if self.browser is None:
            return
        self.browser.deleteLater()
        self.browser = None
        self._set(browserOpen=False)
        QTimer.singleShot(700, self._reopen_reader)

    def _reopen_reader(self):
        if self.page is None and self.browser is None:
            self._create_profile()
            self.refresh()

    def shutdown(self):
        self.api.shutdown()
        self.api.server_close()
        if self.browser and self.browser.state() != QProcess.ProcessState.NotRunning:
            self.browser.terminate()
        self._destroy_profile()
        self.app.processEvents()


@pyqtClassInfo("D-Bus Interface", "org.limityai.Widget")
class FullscreenBridge(QObject):
    def __init__(self, reader: Reader):
        super().__init__()
        self.reader = reader

    @pyqtSlot(bool)
    def SetFullscreen(self, value: bool):
        self.reader.set_fullscreen(value)


def main():
    config_path = Path(os.environ.get("LIMITY_CONFIG", Path.home() / ".config/limity-ai-widget/config.json"))
    config = json.loads(config_path.read_text())
    root = Path(config["dataDir"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    reader = Reader(app, config, root)
    bridge = FullscreenBridge(reader)
    bus = QDBusConnection.sessionBus()
    if bus.isConnected() and bus.registerService("org.limityai.Widget"):
        bus.registerObject("/Status", bridge, QDBusConnection.RegisterOption.ExportAllSlots)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    app.aboutToQuit.connect(reader.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
