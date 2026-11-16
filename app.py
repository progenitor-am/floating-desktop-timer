import sys
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from time import monotonic

from PySide6.QtCore import Qt, QTimer, QPoint, QSettings, QRect
from PySide6.QtGui import QColor, QFont, QKeySequence, QKeySequenceEdit, QAction
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QDialogButtonBox, QVBoxLayout, QMessageBox, QHBoxLayout, QPushButton
)

APP_ORG = "FloatingTimerProject"
APP_NAME = "FloatingDesktopTimer"

# Windows RegisterHotKey constants. The application uses the OS-level API so
# shortcuts continue working while another program has focus.
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
HOTKEY_START_STOP = 1
HOTKEY_RESET = 2

VK_MAP = {**{str(i): 0x30 + i for i in range(10)},
          **{chr(i): i for i in range(ord("A"), ord("Z") + 1)}}
VK_MAP.update({
    "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "ESC": 0x1B,
    "ESCAPE": 0x1B, "F1": 0x70, "F2": 0x71, "F3": 0x72,
    "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76,
    "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A,
    "F12": 0x7B,
})


def parse_hotkey(sequence_text):
    """Convert a simple Qt shortcut such as 'Alt+5' into Win32 modifiers/VK."""
    parts = [p.strip().upper() for p in sequence_text.split("+") if p.strip()]
    modifiers = 0
    key = None
    for part in parts:
        if part in ("ALT",):
            modifiers |= MOD_ALT
        elif part in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif part == "SHIFT":
            modifiers |= MOD_SHIFT
        elif part in ("WIN", "META"):
            modifiers |= MOD_WIN
        else:
            if key is not None:
                raise ValueError("Use one non-modifier key per shortcut.")
            key = part
    if key is None or key not in VK_MAP:
        raise ValueError("Use a supported key: A-Z, 0-9, Space, Tab, Enter, Esc, or F1-F12.")
    if not modifiers:
        raise ValueError("A global shortcut must include at least one modifier.")
    return modifiers, VK_MAP[key]


def format_duration(seconds):
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{secs:02d}"


class DurationDialog(QDialog):
    def __init__(self, parent=None, initial_seconds=300):
        super().__init__(parent)
        self.setWindowTitle("Countdown duration")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.days = QSpinBox(); self.days.setRange(0, 9999)
        self.hours = QSpinBox(); self.hours.setRange(0, 23)
        self.minutes = QSpinBox(); self.minutes.setRange(0, 59)
        self.seconds = QSpinBox(); self.seconds.setRange(0, 59)
        d, r = divmod(max(0, initial_seconds), 86400)
        h, r = divmod(r, 3600); m, s = divmod(r, 60)
        self.days.setValue(d); self.hours.setValue(h)
        self.minutes.setValue(m); self.seconds.setValue(s)
        form.addRow("Days", self.days); form.addRow("Hours", self.hours)
        form.addRow("Minutes", self.minutes); form.addRow("Seconds", self.seconds)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def duration(self):
        return (self.days.value() * 86400 + self.hours.value() * 3600
                + self.minutes.value() * 60 + self.seconds.value())


class HotkeyDialog(QDialog):
    def __init__(self, parent, start_text, reset_text):
        super().__init__(parent)
        self.setWindowTitle("Configure global hotkeys")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.start_edit = QKeySequenceEdit(QKeySequence(start_text))
        self.reset_edit = QKeySequenceEdit(QKeySequence(reset_text))
        form.addRow("Start / Stop", self.start_edit)
        form.addRow("Reset", self.reset_edit)
        layout.addLayout(form)
        note = QLabel("Use a modifier (Alt, Ctrl, Shift, or Win) plus one key.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return (self.start_edit.keySequence().toString(),
                self.reset_edit.keySequence().toString())


class FloatingTimer(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.mode = self.settings.value("mode", "elapsed")
        if self.mode not in ("elapsed", "countdown"):
            self.mode = "elapsed"

        self.elapsed_total = 0.0
        self.elapsed_started_at = None
        self.countdown_duration = int(self.settings.value("countdown_duration", 300))
        self.countdown_remaining = float(self.countdown_duration)
        self.countdown_started_at = None

        self.start_hotkey = self.settings.value("hotkey_start", "Alt+5")
        self.reset_hotkey = self.settings.value("hotkey_reset", "Alt+6")
        self.font_color = self.settings.value("font_color", "#FFFFFF")
        self.background_color = self.settings.value("background_color", "#202020")
        self.background_opacity = int(self.settings.value("background_opacity", 0))

        self._drag_pos = None
        self._resize_origin = None
        self._resize_geometry = None
        self._resize_edges = set()
        self._edge_margin = 8
        self._hotkeys_registered = []

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(150, 55)
        self.setMouseTracking(True)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.label.setStyleSheet("background: transparent;")
        self.label.setFont(QFont("Segoe UI", 25, QFont.DemiBold))

        self.tick = QTimer(self)
        self.tick.setInterval(200)
        self.tick.timeout.connect(self.refresh_display)
        self.tick.start()

        self.apply_appearance()
        self.restore_geometry()
        self.refresh_display()
        self.register_hotkeys()

    def restore_geometry(self):
        x = int(self.settings.value("x", 300))
        y = int(self.settings.value("y", 200))
        w = int(self.settings.value("width", 330))
        h = int(self.settings.value("height", 90))
        self.setGeometry(x, y, max(150, w), max(55, h))

    def save_settings(self):
        g = self.geometry()
        self.settings.setValue("x", g.x()); self.settings.setValue("y", g.y())
        self.settings.setValue("width", g.width()); self.settings.setValue("height", g.height())
        self.settings.setValue("mode", self.mode)
        self.settings.setValue("countdown_duration", self.countdown_duration)
        self.settings.setValue("hotkey_start", self.start_hotkey)
        self.settings.setValue("hotkey_reset", self.reset_hotkey)
        self.settings.setValue("font_color", self.font_color)
        self.settings.setValue("background_color", self.background_color)
        self.settings.setValue("background_opacity", self.background_opacity)
        self.settings.sync()

    def apply_appearance(self):
        color = QColor(self.background_color)
        color.setAlpha(max(0, min(255, self.background_opacity)))
        self.setStyleSheet(f"QWidget {{ background-color: rgba({color.red()},"
                           f"{color.green()},{color.blue()},{color.alpha()});"
                           " border: none; }}")
        self.label.setStyleSheet(f"QLabel {{ color: {self.font_color}; background: transparent; }}")
        self.label.setFont(QFont("Segoe UI", max(10, int(self.height() * 0.34)), QFont.DemiBold))
        self.label.setGeometry(self.rect())

    def resizeEvent(self, event):
        self.label.setGeometry(self.rect())
        self.label.setFont(QFont("Segoe UI", max(10, int(self.height() * 0.34)), QFont.DemiBold))
        super().resizeEvent(event)

    def current_value(self):
        if self.mode == "elapsed":
            if self.elapsed_started_at is not None:
                return self.elapsed_total + (monotonic() - self.elapsed_started_at)
            return self.elapsed_total
        if self.countdown_started_at is not None:
            return max(0.0, self.countdown_remaining -
                       (monotonic() - self.countdown_started_at))
        return max(0.0, self.countdown_remaining)

    def refresh_display(self):
        value = self.current_value()
        self.label.setText(format_duration(value))
        if self.mode == "countdown" and value <= 0 and self.countdown_started_at is not None:
            self.countdown_remaining = 0.0
            self.countdown_started_at = None

    def start(self):
        if self.mode == "elapsed":
            if self.elapsed_started_at is None:
                self.elapsed_started_at = monotonic()
        elif self.countdown_started_at is None and self.countdown_remaining > 0:
            self.countdown_started_at = monotonic()
        self.refresh_display()

    def stop(self):
        if self.mode == "elapsed" and self.elapsed_started_at is not None:
            self.elapsed_total += monotonic() - self.elapsed_started_at
            self.elapsed_started_at = None
        elif self.mode == "countdown" and self.countdown_started_at is not None:
            self.countdown_remaining = self.current_value()
            self.countdown_started_at = None
        self.refresh_display()

    def toggle_start_stop(self):
        running = (self.elapsed_started_at is not None if self.mode == "elapsed"
                   else self.countdown_started_at is not None)
        self.stop() if running else self.start()

    def reset(self):
        if self.mode == "elapsed":
            self.elapsed_total = 0.0
            self.elapsed_started_at = None
        else:
            self.countdown_started_at = None
            self.countdown_remaining = float(self.countdown_duration)
        self.refresh_display()

    def switch_mode(self, new_mode):
        if new_mode == self.mode:
            return
        # Pause the active mode before switching. Each mode retains its own value.
        self.stop()
        self.mode = new_mode
        if new_mode == "countdown":
            self.configure_countdown()
        self.refresh_display()
        self.save_settings()

    def configure_countdown(self):
        self.stop()
        dialog = DurationDialog(self, self.countdown_duration)
        if dialog.exec() == QDialog.Accepted:
            self.countdown_duration = dialog.duration()
            self.countdown_remaining = float(self.countdown_duration)
            self.countdown_started_at = None
            self.save_settings()
        self.refresh_display()

    def choose_font_color(self):
        color = QColorDialog.getColor(QColor(self.font_color), self, "Choose font color")
        if color.isValid():
            self.font_color = color.name()
            self.apply_appearance(); self.save_settings()

    def choose_background_color(self):
        color = QColorDialog.getColor(QColor(self.background_color), self,
                                      "Choose background color")
        if color.isValid():
            self.background_color = color.name()
            # Keep the current alpha/opacity setting; default remains fully transparent.
            self.apply_appearance(); self.save_settings()

    def set_opacity(self):
        dialog = QDialog(self); dialog.setWindowTitle("Background opacity")
        layout = QVBoxLayout(dialog)
        form = QFormLayout(); spin = QSpinBox()
        spin.setRange(0, 255); spin.setValue(self.background_opacity)
        form.addRow("Opacity (0 = transparent, 255 = opaque)", spin)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            self.background_opacity = spin.value()
            self.apply_appearance(); self.save_settings()

    def configure_hotkeys(self):
        dialog = HotkeyDialog(self, self.start_hotkey, self.reset_hotkey)
        if dialog.exec() != QDialog.Accepted:
            return
        start_text, reset_text = dialog.values()
        try:
            start_spec = parse_hotkey(start_text)
            reset_spec = parse_hotkey(reset_text)
            if start_spec == reset_spec:
                raise ValueError("The two shortcuts must be different.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid shortcut", str(exc)); return

        old_start, old_reset = self.start_hotkey, self.reset_hotkey
        self.unregister_hotkeys()
        self.start_hotkey, self.reset_hotkey = start_text, reset_text
        if not self.register_hotkeys():
            self.start_hotkey, self.reset_hotkey = old_start, old_reset
            self.register_hotkeys()
            QMessageBox.warning(self, "Hotkey unavailable",
                                "Windows could not register one or more shortcuts. "
                                "They may already be used by another application.")
        else:
            self.save_settings()

    def register_hotkeys(self):
        if sys.platform != "win32":
            return True
        user32 = ctypes.windll.user32
        success = True
        for hotkey_id, text in ((HOTKEY_START_STOP, self.start_hotkey),
                                (HOTKEY_RESET, self.reset_hotkey)):
            try:
                modifiers, vk = parse_hotkey(text)
            except ValueError:
                success = False
                break
            if user32.RegisterHotKey(int(self.winId()), hotkey_id, modifiers, vk):
                self._hotkeys_registered.append(hotkey_id)
            else:
                success = False
                break
        # Treat the pair as one configuration: don't leave only one shortcut
        # active if the other one could not be registered.
        if not success:
            self.unregister_hotkeys()
        return success

    def unregister_hotkeys(self):
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            for hotkey_id in self._hotkeys_registered:
                user32.UnregisterHotKey(int(self.winId()), hotkey_id)
        self._hotkeys_registered.clear()

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_START_STOP:
                    self.toggle_start_stop()
                elif msg.wParam == HOTKEY_RESET:
                    self.reset()
                return True, 0
        return super().nativeEvent(event_type, message)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Start", self.start)
        menu.addAction("Stop", self.stop)
        menu.addAction("Reset", self.reset)
        menu.addSeparator()
        menu.addAction("Elapsed Time Mode", lambda: self.switch_mode("elapsed"))
        menu.addAction("Countdown Timer Mode", lambda: self.switch_mode("countdown"))
        menu.addAction("Configure Countdown…", self.configure_countdown)
        menu.addSeparator()
        menu.addAction("Set Hotkeys…", self.configure_hotkeys)
        menu.addAction("Change Font Color…", self.choose_font_color)
        menu.addAction("Change Background Color…", self.choose_background_color)
        menu.addAction("Background Opacity…", self.set_opacity)
        menu.addSeparator()
        menu.addAction("Close", self.close)
        menu.exec(event.globalPos())

    def edge_at(self, pos):
        edges = set()
        if pos.x() <= self._edge_margin: edges.add("left")
        elif pos.x() >= self.width() - self._edge_margin: edges.add("right")
        if pos.y() <= self._edge_margin: edges.add("top")
        elif pos.y() >= self.height() - self._edge_margin: edges.add("bottom")
        return edges

    def update_cursor(self, edges):
        if edges in ({"left", "top"}, {"right", "bottom"}):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in ({"right", "top"}, {"left", "bottom"}):
            self.setCursor(Qt.SizeBDiagCursor)
        elif "left" in edges or "right" in edges:
            self.setCursor(Qt.SizeHorCursor)
        elif "top" in edges or "bottom" in edges:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edges = self.edge_at(event.position().toPoint())
            if edges:
                self._resize_edges = edges
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geometry = self.geometry()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._resize_origin is not None:
            delta = event.globalPosition().toPoint() - self._resize_origin
            g = QRect(self._resize_geometry)
            if "left" in self._resize_edges: g.setLeft(g.left() + delta.x())
            if "right" in self._resize_edges: g.setRight(g.right() + delta.x())
            if "top" in self._resize_edges: g.setTop(g.top() + delta.y())
            if "bottom" in self._resize_edges: g.setBottom(g.bottom() + delta.y())
            if g.width() >= self.minimumWidth() and g.height() >= self.minimumHeight():
                self.setGeometry(g)
            event.accept(); return
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept(); return
        self.update_cursor(self.edge_at(pos))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_origin = None
        self._resize_geometry = None
        self._resize_edges = set()
        self.save_settings()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self.stop()
        self.unregister_hotkeys()
        self.save_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)
    timer = FloatingTimer()
    timer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
