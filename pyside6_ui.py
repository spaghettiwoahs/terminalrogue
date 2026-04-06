from __future__ import annotations

import builtins
import os
import re
import shlex
import sys
import threading
from datetime import datetime

from PySide6.QtCore import QEvent, QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontInfo,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPen,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from game_state import GameState
from payload_docs import flag_effect_lines, item_effect_lines, script_effect_lines, target_effect_lines
from tcod_ui import TcodTerminalApp
from ui_flavor import (
    BOOT_MENU_CONTINUE_STATUS,
    BOOT_MENU_DEFAULT_STATUS,
    BOOT_MENU_DEFAULT_SUBTITLE,
    BOOT_MENU_FOOTER,
    BOOT_MENU_LABELS,
    BOOT_MENU_TITLE,
    black_ice_overlay,
    build_boot_tutorial_overlay,
    build_drone_tutorial_overlay,
    build_warmup_gate_overlay,
    databank_staging_text,
    dev_console_banner_lines,
    get_boot_menu_loading_copy,
    get_tutorial_boot_steps,
    isolated_route_text,
    log_staging_text,
    objective_staging_text,
    player_staging_text,
    route_staging_text,
    sandbox_alert_overlay,
    target_idle_text,
    target_staging_text,
)


BASE_PALETTE = {
    "desktop_top": "#0a0d14",
    "desktop_bottom": "#0f1420",
    "desktop_edge": "#1a2333",
    "desktop_glow": "#13253d",
    "panel": "#141b27",
    "panel_alt": "#101621",
    "panel_border": "#293246",
    "panel_border_active": "#5f8cff",
    "header": "#1a2130",
    "header_active": "#202b3f",
    "terminal": "#0d121b",
    "terminal_alt": "#111827",
    "dock": "#111722",
    "text": "#e8edf7",
    "muted": "#8a94a6",
    "cyan": "#73d0ff",
    "green": "#7fde98",
    "yellow": "#f0c674",
    "red": "#ff7b72",
    "magenta": "#c792ea",
    "white": "#f7faff",
    "accent": "#74a7ff",
    "accent_soft": "#1a2a46",
}

COLOR_SCHEMES = {
    "Midnight": {},
    "Nord": {
        "desktop_top": "#0b1220",
        "desktop_bottom": "#111a2e",
        "desktop_edge": "#22314c",
        "desktop_glow": "#213754",
        "panel": "#161f32",
        "panel_alt": "#111a2a",
        "panel_border": "#334661",
        "panel_border_active": "#88c0d0",
        "header": "#1b263b",
        "header_active": "#22324b",
        "terminal": "#0f1726",
        "terminal_alt": "#162033",
        "dock": "#121b2a",
        "text": "#e5e9f0",
        "muted": "#9aa7ba",
        "cyan": "#88c0d0",
        "green": "#a3be8c",
        "yellow": "#ebcb8b",
        "red": "#bf616a",
        "magenta": "#b48ead",
        "white": "#f4f7fb",
        "accent": "#81a1c1",
        "accent_soft": "#1e3147",
    },
    "Matrix": {
        "desktop_top": "#08110c",
        "desktop_bottom": "#0d1711",
        "desktop_edge": "#183023",
        "desktop_glow": "#1f4930",
        "panel": "#101a13",
        "panel_alt": "#0d140f",
        "panel_border": "#264232",
        "panel_border_active": "#63e38f",
        "header": "#132016",
        "header_active": "#18301e",
        "terminal": "#090f0b",
        "terminal_alt": "#0e1611",
        "dock": "#0d140f",
        "text": "#d9ffe1",
        "muted": "#85b38f",
        "cyan": "#7bf7d4",
        "green": "#6df08b",
        "yellow": "#d6ff72",
        "red": "#ff7f7f",
        "magenta": "#9fd88d",
        "white": "#f1fff4",
        "accent": "#63e38f",
        "accent_soft": "#153322",
    },
    "Amber": {
        "desktop_top": "#120d09",
        "desktop_bottom": "#1a130d",
        "desktop_edge": "#342318",
        "desktop_glow": "#533521",
        "panel": "#1a140f",
        "panel_alt": "#15100c",
        "panel_border": "#4b3522",
        "panel_border_active": "#ffbf69",
        "header": "#231a12",
        "header_active": "#302216",
        "terminal": "#110d09",
        "terminal_alt": "#18120d",
        "dock": "#17110d",
        "text": "#ffe3bf",
        "muted": "#c3a27b",
        "cyan": "#ffd28a",
        "green": "#c7f08a",
        "yellow": "#ffcc66",
        "red": "#ff8f6b",
        "magenta": "#f0b27a",
        "white": "#fff5e8",
        "accent": "#ffbf69",
        "accent_soft": "#3d2a17",
    },
}

PALETTE = dict(BASE_PALETTE)

TASKBAR_LABELS = {
    "terminal": "terminal",
    "log": "log",
    "player": "player",
    "target": "target",
    "objective": "objective",
    "route": "routeweb",
    "databank": "databank",
    "settings": "settings",
    "payload": "payload",
    "tutorial": "coach",
    "dev": "dev",
}


def repolish(widget: QWidget):
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def build_char_format(color: str, *, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.DemiBold)
    return fmt


def pick_font(candidates: list[str], *, point_size: int, fixed: bool) -> QFont:
    fallback_families = (
        ["Cascadia Mono", "Consolas", "Lucida Console", "Courier New"]
        if fixed
        else ["Segoe UI Variable Text", "Segoe UI", "Tahoma", "Arial"]
    )
    generic_families = {"sans serif", "monospace", "serif"}

    for family in [*candidates, *fallback_families]:
        font = QFont(family)
        font.setPointSize(point_size)
        if fixed:
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setFixedPitch(True)
        resolved = QFontInfo(font).family().strip().lower()
        if resolved and resolved not in generic_families:
            return font

    font = QFont("Consolas" if fixed else "Segoe UI")
    font.setPointSize(point_size)
    if fixed:
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
    return font


class PySideGameBackend(TcodTerminalApp):
    """Run the existing controller behind a Qt desktop shell."""

    def run_game(self):
        original_print = builtins.print

        def captured_print(*args, sep=" ", end="\n", file=None, flush=False):
            if file not in {None, sys.stdout, sys.stderr}:
                original_print(*args, sep=sep, end=end, file=file, flush=flush)
                return
            rendered = sep.join(str(arg) for arg in args) + end
            self.write(rendered)

        builtins.print = captured_print
        try:
            super().run_game()
        finally:
            builtins.print = original_print

    def get_ascii_art(self, art_key: str):
        return ""

    def start(self):
        if self.game_thread and self.game_thread.is_alive():
            return
        self.running = True
        self.game_thread = threading.Thread(target=self.run_game, daemon=True)
        self.game_thread.start()


class TerminalPane(QFrame):
    def __init__(self, *, wrap_text: bool = True):
        super().__init__()
        self.setObjectName("paneSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.body = QPlainTextEdit()
        self.body.setObjectName("paneBody")
        self.body.setReadOnly(True)
        self.body.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.body.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        if wrap_text:
            self.body.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self.body.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.body, 1)

    def set_text(self, text: str):
        if self.body.toPlainText() != text:
            self.body.setPlainText(text)


class LiveLogPane(TerminalPane):
    def __init__(self):
        super().__init__(wrap_text=True)
        self._follow_tail = True
        self.body.verticalScrollBar().valueChanged.connect(self._track_scroll_position)

    def _track_scroll_position(self, value: int):
        bar = self.body.verticalScrollBar()
        self._follow_tail = value >= max(0, bar.maximum() - 2)

    def set_text(self, text: str):
        if self.body.toPlainText() == text:
            return
        bar = self.body.verticalScrollBar()
        bottom_offset = max(0, bar.maximum() - bar.value())
        was_following = self._follow_tail or bar.value() >= max(0, bar.maximum() - 2)
        self.body.setPlainText(text)
        if was_following:
            bar.setValue(bar.maximum())
        else:
            bar.setValue(max(0, bar.maximum() - bottom_offset))


class DatabankPane(TerminalPane):
    def __init__(self, entry_provider, open_entry):
        super().__init__(wrap_text=True)
        self.entry_provider = entry_provider
        self.open_entry = open_entry
        self.body.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.body.setMouseTracking(True)
        self.body.viewport().setMouseTracking(True)
        self.body.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.body.viewport():
            if event.type() == QEvent.Type.MouseMove:
                cursor = self.body.cursorForPosition(event.pos())
                hovered_line = cursor.block().text()
                entry = self.entry_provider(hovered_line)
                cursor_shape = Qt.CursorShape.PointingHandCursor if entry else Qt.CursorShape.ArrowCursor
                if self.body.viewport().cursor().shape() != cursor_shape:
                    self.body.viewport().setCursor(cursor_shape)
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                cursor = self.body.cursorForPosition(event.pos())
                cursor.clearSelection()
                self.body.setTextCursor(cursor)
                hovered_line = cursor.block().text()
                entry = self.entry_provider(hovered_line)
                if entry:
                    self.open_entry(entry)
                    return True
            elif event.type() == QEvent.Type.Leave:
                self.body.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)


class ObjectivePane(TerminalPane):
    def __init__(self, open_tutorial):
        super().__init__(wrap_text=True)
        self.open_tutorial = open_tutorial
        self.body.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.body.setMouseTracking(True)
        self.body.viewport().setMouseTracking(True)
        self.body.viewport().installEventFilter(self)

    @staticmethod
    def is_tutorial_line(line: str) -> bool:
        return "open tutorial coach" in line.strip().lower()

    def eventFilter(self, obj, event):
        if obj is self.body.viewport():
            if event.type() == QEvent.Type.MouseMove:
                cursor = self.body.cursorForPosition(event.pos())
                hovered_line = cursor.block().text()
                cursor_shape = (
                    Qt.CursorShape.PointingHandCursor
                    if self.is_tutorial_line(hovered_line)
                    else Qt.CursorShape.ArrowCursor
                )
                if self.body.viewport().cursor().shape() != cursor_shape:
                    self.body.viewport().setCursor(cursor_shape)
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                cursor = self.body.cursorForPosition(event.pos())
                hovered_line = cursor.block().text()
                if self.is_tutorial_line(hovered_line):
                    self.open_tutorial()
                    return True
            elif event.type() == QEvent.Type.Leave:
                self.body.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)


class TutorialPane(TerminalPane):
    clicked = Signal()

    def __init__(self):
        super().__init__(wrap_text=True)
        self.body.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.body.setMouseTracking(True)
        self.body.viewport().setMouseTracking(True)
        self.body.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.body.viewport():
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
                return True
        return super().eventFilter(obj, event)


class BootMenuOverlay(QFrame):
    new_tutorial = Signal()
    skip_tutorial = Signal()
    continue_requested = Signal()
    quit_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("bootMenuOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._default_status = BOOT_MENU_DEFAULT_STATUS
        self._default_subtitle = BOOT_MENU_DEFAULT_SUBTITLE

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(12)

        self.title = QLabel(BOOT_MENU_TITLE)
        self.title.setObjectName("bootMenuTitle")
        layout.addWidget(self.title)

        self.subtitle = QLabel(self._default_subtitle)
        self.subtitle.setObjectName("bootMenuSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.status = QLabel(self._default_status)
        self.status.setObjectName("bootMenuStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tutorial_button = QPushButton(BOOT_MENU_LABELS["new_tutorial"])
        self.tutorial_button.setObjectName("bootMenuButton")
        self.tutorial_button.clicked.connect(self.new_tutorial.emit)
        layout.addWidget(self.tutorial_button)

        self.skip_button = QPushButton(BOOT_MENU_LABELS["skip_tutorial"])
        self.skip_button.setObjectName("bootMenuButton")
        self.skip_button.clicked.connect(self.skip_tutorial.emit)
        layout.addWidget(self.skip_button)

        self.continue_button = QPushButton(BOOT_MENU_LABELS["continue"])
        self.continue_button.setObjectName("bootMenuButton")
        self.continue_button.clicked.connect(self.continue_requested.emit)
        layout.addWidget(self.continue_button)

        self.quit_button = QPushButton(BOOT_MENU_LABELS["quit"])
        self.quit_button.setObjectName("bootMenuButton")
        self.quit_button.setProperty("role", "danger")
        self.quit_button.clicked.connect(self.quit_requested.emit)
        layout.addWidget(self.quit_button)

        self.footer = QLabel(BOOT_MENU_FOOTER)
        self.footer.setObjectName("bootMenuFooter")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)

        layout.addStretch(1)

    def set_continue_available(self, available: bool):
        self.continue_button.setEnabled(available)
        self.status.setText(BOOT_MENU_CONTINUE_STATUS[available])

    def set_busy(self, busy: bool, *, subtitle: str | None = None, status: str | None = None):
        for button in (
            self.tutorial_button,
            self.skip_button,
            self.continue_button,
            self.quit_button,
        ):
            button.setEnabled(not busy)
        self.subtitle.setText(subtitle or self._default_subtitle)
        if status is not None:
            self.status.setText(status)
        elif not busy:
            self.status.setText(self._default_status)


class SettingsPane(QFrame):
    theme_changed = Signal(str)
    font_bias_changed = Signal(int)
    reset_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("settingsPane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title = QLabel("Display Settings")
        self.title.setObjectName("settingsTitle")
        layout.addWidget(self.title)

        self.note = QLabel("Changes apply live to the current session.")
        self.note.setObjectName("settingsNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setHorizontalSpacing(12)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("settingsCombo")
        self.theme_combo.addItems(list(COLOR_SCHEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        form.addRow("Color Scheme", self.theme_combo)

        self.font_bias_spin = QSpinBox()
        self.font_bias_spin.setObjectName("settingsSpin")
        self.font_bias_spin.setRange(-3, 6)
        self.font_bias_spin.setPrefix(" ")
        self.font_bias_spin.setSuffix(" step")
        self.font_bias_spin.valueChanged.connect(self.font_bias_changed.emit)
        form.addRow("Font Size", self.font_bias_spin)

        layout.addLayout(form)

        self.reset_button = QPushButton("reset to defaults")
        self.reset_button.setObjectName("settingsReset")
        self.reset_button.clicked.connect(self.reset_requested.emit)
        layout.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

    def set_values(self, theme_name: str, font_bias: int):
        blocked = self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(theme_name)
        self.theme_combo.blockSignals(blocked)

        blocked = self.font_bias_spin.blockSignals(True)
        self.font_bias_spin.setValue(font_bias)
        self.font_bias_spin.blockSignals(blocked)


class TerminalConsole(QPlainTextEdit):
    command_submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("feed")
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setTabChangesFocus(False)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.history_lines: list[str] = []
        self.history_tones: list[str] = []
        self.prompt_text = ""
        self.current_input = ""
        self.prompt_active = False
        self.input_locked = False
        self._render_cache = ""

    def set_history(self, snapshot: list[tuple[str, str]]) -> bool:
        lines = [line for line, _tone in snapshot]
        tones = [tone for _line, tone in snapshot]
        if lines == self.history_lines and tones == self.history_tones:
            return False
        self.history_lines = lines
        self.history_tones = tones
        self._sync_view()
        return True

    def set_prompt_state(self, prompt: str, active: bool):
        if self.prompt_text == prompt and self.prompt_active == active:
            return
        self.prompt_text = prompt
        self.prompt_active = active
        if not active:
            self.current_input = ""
        self._sync_view()

    def move_cursor_to_end(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _compose_text(self) -> tuple[str, int, str]:
        history_text = "\n".join(self.history_lines)
        prompt_index = -1
        prompt_line = ""
        if self.prompt_active:
            prompt_line = f"{self.prompt_text}{self.current_input}"
            prompt_index = len(self.history_lines)
            if history_text:
                return history_text + "\n" + prompt_line, prompt_index, self.prompt_text
            return prompt_line, prompt_index, self.prompt_text
        return history_text, prompt_index, prompt_line

    def _sync_view(self):
        text, _prompt_index, _prompt_prefix = self._compose_text()
        if text != self._render_cache:
            scroll_bar = self.verticalScrollBar()
            at_bottom = scroll_bar.value() >= scroll_bar.maximum() - 2
            self.setPlainText(text)
            self._render_cache = text
            if at_bottom:
                self.move_cursor_to_end()

    def keyPressEvent(self, event):
        copy_match = event.matches(QKeySequence.StandardKey.Copy)
        paste_match = event.matches(QKeySequence.StandardKey.Paste)

        if self.input_locked:
            if copy_match:
                super().keyPressEvent(event)
            else:
                event.ignore()
            return

        if not self.prompt_active:
            if copy_match:
                super().keyPressEvent(event)
            else:
                event.ignore()
            return

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        if key in {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta}:
            return

        if modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_L:
            self.current_input = ""
            self._sync_view()
            self.command_submitted.emit("cls")
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            command = self.current_input
            self.current_input = ""
            self._sync_view()
            self.command_submitted.emit(command)
            return

        if key == Qt.Key.Key_Backspace:
            if self.current_input:
                self.current_input = self.current_input[:-1]
                self._sync_view()
            return

        if key == Qt.Key.Key_Escape:
            self.current_input = ""
            self._sync_view()
            return

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            self.move_cursor_to_end()
            return

        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            if paste_match:
                pasted = QApplication.clipboard().text().replace("\r", "").replace("\n", " ")
                if pasted:
                    self.current_input += pasted
                    self._sync_view()
            elif copy_match:
                super().keyPressEvent(event)
            return

        if text and text >= " ":
            self.current_input += text
            self._sync_view()
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.move_cursor_to_end()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.move_cursor_to_end()


class TerminalShell(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("terminalSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.viewport = QFrame()
        self.viewport.setObjectName("terminalViewport")
        viewport_layout = QVBoxLayout(self.viewport)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)

        self.feed = TerminalConsole()
        viewport_layout.addWidget(self.feed, 1)
        layout.addWidget(self.viewport, 1)


class FeedHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.line_tones: list[str] = []
        self.prompt_line_index = -1
        self.prompt_prefix = ""
        self.refresh_palette()

    def refresh_palette(self):
        self.formats = {
            tone: build_char_format(color)
            for tone, color in {
                "text": PALETTE["text"],
                "muted": PALETTE["muted"],
                "cyan": PALETTE["cyan"],
                "green": PALETTE["green"],
                "yellow": PALETTE["yellow"],
                "red": PALETTE["red"],
                "magenta": PALETTE["magenta"],
                "white": PALETTE["white"],
            }.items()
        }
        self.prompt_format = build_char_format(PALETTE["green"], bold=True)
        self.input_format = build_char_format(PALETTE["text"])
        self.rehighlight()

    def set_line_tones(self, tones: list[str]):
        self.line_tones = tones
        self.rehighlight()

    def set_live_prompt(self, line_index: int, prompt_prefix: str):
        self.prompt_line_index = line_index
        self.prompt_prefix = prompt_prefix
        self.rehighlight()

    def highlightBlock(self, text: str):
        block_number = self.currentBlock().blockNumber()
        if block_number == self.prompt_line_index:
            prefix_len = min(len(self.prompt_prefix), len(text))
            if prefix_len:
                self.setFormat(0, prefix_len, self.prompt_format)
            if len(text) > prefix_len:
                self.setFormat(prefix_len, len(text) - prefix_len, self.input_format)
            return
        tone = self.line_tones[block_number] if block_number < len(self.line_tones) else "text"
        self.setFormat(0, len(text), self.formats.get(tone, self.formats["text"]))


class PanelHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.refresh_palette()

    def refresh_palette(self):
        self.rules = [
            (re.compile(r"^TUTORIAL ACTIVE$"), build_char_format(PALETTE["magenta"], bold=True)),
            (re.compile(r"^(TRY:.*)$"), build_char_format(PALETTE["yellow"], bold=True)),
            (re.compile(r"^(WHY:.*)$"), build_char_format(PALETTE["cyan"])),
            (re.compile(r"^(LOOK:.*|CLICK:.*)$"), build_char_format(PALETTE["green"], bold=True)),
            (re.compile(r"^(\[layer \d+\])$"), build_char_format(PALETTE["yellow"], bold=True)),
            (re.compile(r"^[A-Z0-9 /:_-]{6,}$"), build_char_format(PALETTE["cyan"], bold=True)),
            (
                re.compile(
                    r"^(HOST|WEAPON|COUNTER|ENTRY|EXPOSURE|INTENT|WEAK POINT|VULN|ADAPT|DEFENSE|HANDLE|TITLE|DAY|WALLET|TRACE|RAM|SIGNATURE|ITEMS|LOCAL IP|BOT BAY|CLASS GUIDE|OWNER|ROLE|NETRANGE|OPERATING|INTEL|SUBSYSTEMS|LINK|PORTS)\b"
                ),
                build_char_format(PALETTE["cyan"], bold=True),
            ),
            (re.compile(r"\b(OS|SEC|NET|MEM|STO)\b"), build_char_format(PALETTE["accent"], bold=True)),
            (re.compile(r"\b(CLEARED|MARKET|LIVE|SCANNED|AVAILABLE|DONE|TRACKING)\b"), build_char_format(PALETTE["green"], bold=True)),
            (re.compile(r"\b(WARM|TRACE|WARNING|ALERT)\b"), build_char_format(PALETTE["yellow"], bold=True)),
            (re.compile(r"\b(HOT|LOCKED|FINAL|FAILED|BURNED|TERMINATED)\b"), build_char_format(PALETTE["red"], bold=True)),
            (re.compile(r"^(mail =.*|bot =.*)$"), build_char_format(PALETTE["cyan"])),
            (re.compile(r"^(recon ladder:|host architecture)$"), build_char_format(PALETTE["cyan"], bold=True)),
        ]
        self.rehighlight()

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class ArchiveHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.refresh_palette()

    def refresh_palette(self):
        self.default_format = build_char_format(PALETTE["text"])
        self.header_format = build_char_format(PALETTE["cyan"], bold=True)
        self.tag_formats = {
            "SYS": build_char_format(PALETTE["cyan"], bold=True),
            "CMD": build_char_format(PALETTE["green"], bold=True),
            "OK": build_char_format(PALETTE["green"], bold=True),
            "WARN": build_char_format(PALETTE["yellow"], bold=True),
            "ERR": build_char_format(PALETTE["red"], bold=True),
            "OPS": build_char_format(PALETTE["white"], bold=True),
            "BOT": build_char_format(PALETTE["magenta"], bold=True),
            "NOTE": build_char_format(PALETTE["magenta"], bold=True),
            "INFO": build_char_format(PALETTE["muted"], bold=True),
        }
        self.rehighlight()

    def highlightBlock(self, text: str):
        self.setFormat(0, len(text), self.default_format)
        stripped = text.strip()
        if not stripped:
            return
        if stripped.startswith("SESSION LOG //") or stripped.startswith("entries:") or stripped.startswith("format:"):
            self.setFormat(0, len(text), self.header_format)
            return

        match = re.match(r"^(\d{2}:\d{2}:\d{2}) \[([A-Z]+)\s*\] (.*)$", text)
        if not match:
            return

        time_end = len(match.group(1))
        tag_start = text.find("[")
        tag_end = text.find("]") + 1
        body_start = match.start(3)

        self.setFormat(0, time_end, build_char_format(PALETTE["muted"]))
        tag = match.group(2).strip()
        self.setFormat(tag_start, tag_end - tag_start, self.tag_formats.get(tag, self.tag_formats["INFO"]))
        body_color = {
            "SYS": PALETTE["text"],
            "CMD": PALETTE["text"],
            "OK": PALETTE["green"],
            "WARN": PALETTE["yellow"],
            "ERR": PALETTE["red"],
            "OPS": PALETTE["text"],
            "BOT": PALETTE["magenta"],
            "NOTE": PALETTE["magenta"],
            "INFO": PALETTE["text"],
        }.get(tag, PALETTE["text"])
        self.setFormat(body_start, len(text) - body_start, build_char_format(body_color))


class StatChip(QFrame):
    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("statChip")
        self.setProperty("kind", "default")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.label = QLabel(label.upper())
        self.label.setObjectName("statChipLabel")
        layout.addWidget(self.label)

        self.value = QLabel("--")
        self.value.setObjectName("statChipValue")
        layout.addWidget(self.value)

    def set_value(self, value: str):
        self.value.setText(value)

    def set_kind(self, kind: str):
        if self.property("kind") != kind:
            self.setProperty("kind", kind)
            repolish(self)


class DesktopCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("desktopCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(PALETTE["desktop_top"]))
        gradient.setColorAt(0.55, QColor(PALETTE["desktop_bottom"]))
        gradient.setColorAt(1.0, QColor("#0b1220"))
        painter.fillRect(rect, gradient)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(24, 42, 70, 38))
        painter.drawEllipse(rect.adjusted(-160, -140, 140, 80))
        painter.setBrush(QColor(96, 140, 255, 18))
        painter.drawEllipse(rect.adjusted(rect.width() // 2, -180, 260, 140))

        painter.setPen(QPen(QColor(PALETTE["desktop_edge"]), 1))
        for offset in range(-rect.height(), rect.width(), 42):
            painter.drawLine(offset, 0, offset + rect.height(), rect.height())

        painter.setPen(QPen(QColor(PALETTE["desktop_glow"]), 1))
        painter.drawLine(rect.left(), rect.bottom() - 2, rect.right(), rect.bottom() - 2)


class ResizeGrip(QWidget):
    drag_started = Signal()

    def __init__(self, window: "FloatingWindow"):
        super().__init__(window)
        self.window = window
        self._dragging = False
        self._origin = QPoint()
        self._start_geometry = QRect()
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("resize")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.window.is_maximized_window:
            self.drag_started.emit()
            self.window.begin_interaction("resize")
            self._dragging = True
            self._origin = event.globalPosition().toPoint()
            self._start_geometry = self.window.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._origin
            self.window.resize_clamped(
                self._start_geometry.width() + delta.x(),
                self._start_geometry.height() + delta.y(),
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self.window.end_interaction()
        self._dragging = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#5f6d86"), 1.2)
        painter.setPen(pen)
        size = self.rect()
        painter.drawLine(size.right() - 11, size.bottom() - 3, size.right() - 3, size.bottom() - 11)
        painter.drawLine(size.right() - 7, size.bottom() - 3, size.right() - 3, size.bottom() - 7)
        painter.drawLine(size.right() - 15, size.bottom() - 3, size.right() - 3, size.bottom() - 15)


class WindowTitleBar(QFrame):
    focused = Signal()
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, window: "FloatingWindow", title: str):
        super().__init__(window)
        self.window = window
        self.setObjectName("windowHeader")
        self._dragging = False
        self._origin = QPoint()
        self._window_origin = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(7)

        self.accent_dot = QLabel()
        self.accent_dot.setObjectName("windowAccentDot")
        self.accent_dot.setFixedSize(10, 10)
        layout.addWidget(self.accent_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("windowTitle")
        layout.addWidget(self.title_label, 1)

        self.min_button = QPushButton("-")
        self.min_button.setObjectName("windowControl")
        self.min_button.setProperty("role", "minimize")
        self.min_button.setFixedSize(22, 22)
        self.min_button.setToolTip("minimize")
        self.min_button.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.min_button)

        self.max_button = QPushButton("[]")
        self.max_button.setObjectName("windowControl")
        self.max_button.setProperty("role", "maximize")
        self.max_button.setFixedSize(22, 22)
        self.max_button.setToolTip("maximize")
        self.max_button.clicked.connect(self.maximize_requested.emit)
        layout.addWidget(self.max_button)

        self.close_button = QPushButton("x")
        self.close_button.setObjectName("windowControl")
        self.close_button.setProperty("role", "close")
        self.close_button.setFixedSize(22, 22)
        self.close_button.setToolTip("hide")
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_button)

    def set_title(self, title: str):
        self.title_label.setText(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.focused.emit()
            if not self.window.is_maximized_window:
                self.window.begin_interaction("move")
                self._dragging = True
                self._origin = event.globalPosition().toPoint()
                self._window_origin = self.window.pos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._origin
            self.window.move_clamped(self._window_origin + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self.window.end_interaction(event.globalPosition().toPoint())
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class FloatingWindow(QFrame):
    activated = Signal(str)
    hidden_from_ui = Signal(str)
    shown_from_ui = Signal(str)

    def __init__(self, key: str, title: str, content: QWidget, parent: QWidget):
        super().__init__(parent)
        self.key = key
        self._normal_geometry: QRect | None = None
        self._interaction_mode: str | None = None
        self.is_maximized_window = False
        self.setObjectName("floatingWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("active", False)
        self.setProperty("guided", False)
        self.setProperty("accent", key)
        self.setMinimumSize(280, 180)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 78))
        self.shadow = shadow
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.header = WindowTitleBar(self, title)
        layout.addWidget(self.header, 0)

        self.content_shell = QFrame()
        self.content_shell.setObjectName("windowContentShell")
        shell_layout = QVBoxLayout(self.content_shell)
        shell_layout.setContentsMargins(6, 6, 6, 6)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(content, 1)
        layout.addWidget(self.content_shell, 1)

        self.grip = ResizeGrip(self)
        self.grip.drag_started.connect(lambda: self.activated.emit(self.key))

        self.header.focused.connect(lambda: self.activated.emit(self.key))
        self.header.minimize_requested.connect(self.minimize_window)
        self.header.maximize_requested.connect(self.toggle_maximized)
        self.header.close_requested.connect(self.hide_window)

        self._install_activation_filters(content)

    def _install_activation_filters(self, widget: QWidget):
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.activated.emit(self.key)
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width() - 8, self.height() - self.grip.height() - 8)
        self.grip.setVisible(not self.is_maximized_window)

    def mousePressEvent(self, event):
        self.activated.emit(self.key)
        super().mousePressEvent(event)

    def set_title(self, title: str):
        self.header.set_title(title)

    def set_active(self, active: bool):
        if self.property("active") != active:
            self.setProperty("active", active)
            repolish(self)
            repolish(self.header)
            repolish(self.content_shell)

    def set_guided(self, guided: bool):
        if self.property("guided") != guided:
            self.setProperty("guided", guided)
            repolish(self)
            repolish(self.header)
            repolish(self.content_shell)

    def begin_interaction(self, mode: str):
        self._interaction_mode = mode
        if self.shadow:
            self.shadow.setEnabled(False)

    def end_interaction(self, global_point: QPoint | None = None):
        if self.shadow:
            self.shadow.setEnabled(True)
        self._interaction_mode = None

    def desktop_rect(self) -> QRect:
        parent = self.parentWidget()
        if not parent:
            return QRect()
        return parent.rect().adjusted(18, 18, -18, -18)

    def fit_to_desktop(self):
        target = self.desktop_rect()
        self.setGeometry(target)
        self.is_maximized_window = True
        self.header.max_button.setText("<>")
        repolish(self)

    def clamp_to_desktop(self):
        if self.isHidden():
            return
        if self.is_maximized_window:
            self.fit_to_desktop()
            return

        bounds = self.desktop_rect()
        if not bounds.isValid():
            return

        width = min(self.width(), bounds.width())
        height = min(self.height(), bounds.height())
        x = min(max(self.x(), bounds.left()), bounds.right() - width)
        y = min(max(self.y(), bounds.top()), bounds.bottom() - height)
        self.setGeometry(x, y, width, height)

    def move_clamped(self, target: QPoint):
        if self.is_maximized_window:
            return
        bounds = self.desktop_rect()
        width = self.width()
        height = self.height()
        x = min(max(target.x(), bounds.left()), bounds.right() - width)
        y = min(max(target.y(), bounds.top()), bounds.bottom() - height)
        self.move(x, y)

    def resize_clamped(self, width: int, height: int):
        if self.is_maximized_window:
            return
        bounds = self.desktop_rect()
        width = max(self.minimumWidth(), min(width, bounds.right() - self.x()))
        height = max(self.minimumHeight(), min(height, bounds.bottom() - self.y()))
        self.resize(width, height)

    def minimize_window(self):
        self.set_active(False)
        self.hide()
        self.hidden_from_ui.emit(self.key)

    def hide_window(self):
        self.set_active(False)
        self.hide()
        self.hidden_from_ui.emit(self.key)

    def restore_window(self):
        self.show()
        self.raise_()
        self.activated.emit(self.key)
        self.shown_from_ui.emit(self.key)

    def toggle_maximized(self):
        if self.is_maximized_window:
            self.is_maximized_window = False
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self.header.max_button.setText("[]")
        else:
            self._normal_geometry = self.geometry()
            self.is_maximized_window = True
            self.fit_to_desktop()
        repolish(self)


class TerminalRoguePySideWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.backend = PySideGameBackend()
        self._prompt_was_active = False
        self._last_log_snapshot: list[tuple[str, str]] = []
        self._initial_layout_done = False
        self._last_tutorial_signature = ""
        self.current_ui_font_size = 10
        self.current_mono_font_size = 11
        self.color_scheme_name = "Midnight"
        self.font_size_bias = 0
        self.floating_windows: dict[str, FloatingWindow] = {}
        self.window_buttons: dict[str, QPushButton] = {}
        self.taskbar_seen_keys: set[str] = set()
        self.primary_window_keys = ("terminal", "log", "player", "target", "objective", "route", "databank")
        self.tutorial_boot_started = False
        self.tutorial_boot_complete = False
        self.tutorial_boot_step = 0
        self.tutorial_boot_revealed: set[str] = set()
        self.tutorial_warmup_requested = False
        self.tutorial_warmup_gate_pending = False
        self.main_menu_active = True
        self.main_menu_pending_choice: str | None = None
        self.dev_log_lines: list[tuple[str, str]] = []
        self.dev_command_history: list[str] = []
        self._dev_last_snapshot: list[tuple[str, str]] = []
        self.dev_bootstrapped = False

        self.setWindowTitle("Terminal Rogue OS")
        self.resize(1600, 980)
        self.build_ui()
        self.apply_theme()
        self.install_click_focus_proxy()
        self.refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_from_backend)
        self.refresh_timer.start(90)

        self.backend.start()

    def build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(12)

        left_block = QVBoxLayout()
        left_block.setContentsMargins(0, 0, 0, 0)
        left_block.setSpacing(2)
        self.brand_label = QLabel("terminal rogue")
        self.brand_label.setObjectName("brandLabel")
        self.session_label = QLabel("launching shell session")
        self.session_label.setObjectName("sessionLabel")
        left_block.addWidget(self.brand_label)
        left_block.addWidget(self.session_label)
        top_layout.addLayout(left_block)

        self.dock = QFrame()
        self.dock.setObjectName("dock")
        self.dock_layout = QHBoxLayout(self.dock)
        self.dock_layout.setContentsMargins(8, 4, 8, 4)
        self.dock_layout.setSpacing(6)
        top_layout.addStretch(1)
        top_layout.addWidget(self.dock, 1)
        top_layout.addStretch(1)

        self.day_chip = StatChip("day")
        self.wallet_chip = StatChip("wallet")
        self.trace_chip = StatChip("trace")
        self.sweep_chip = StatChip("sweep")
        self.status_chip = StatChip("route")
        self.clock_chip = StatChip("time")

        for chip in [self.day_chip, self.wallet_chip, self.trace_chip, self.sweep_chip, self.status_chip, self.clock_chip]:
            top_layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(self.top_bar)

        self.desktop = DesktopCanvas()
        root.addWidget(self.desktop, 1)

        self.boot_menu = BootMenuOverlay()
        self.boot_menu.setParent(self.desktop)
        self.boot_menu.new_tutorial.connect(lambda: self.submit_main_menu_choice("1"))
        self.boot_menu.skip_tutorial.connect(lambda: self.submit_main_menu_choice("2"))
        self.boot_menu.continue_requested.connect(lambda: self.submit_main_menu_choice("3"))
        self.boot_menu.quit_requested.connect(self.close)
        self.boot_menu.show()

        self.shell = TerminalShell()
        self.feed = self.shell.feed
        self.input = self.feed
        self.feed.command_submitted.connect(self.submit_command)
        self.feed_highlighter = FeedHighlighter(self.feed.document())
        self.log_archive = LiveLogPane()

        self.player = TerminalPane()
        self.target = TerminalPane()
        self.objective = ObjectivePane(self.open_tutorial_window)
        self.route = TerminalPane()
        self.databank = DatabankPane(self.lookup_databank_entry, self.open_databank_entry)
        self.dev_shell = TerminalShell()
        self.dev_feed = self.dev_shell.feed
        self.dev_input = self.dev_feed
        self.dev_feed.command_submitted.connect(self.submit_dev_command)
        self.dev_feed_highlighter = FeedHighlighter(self.dev_feed.document())
        self.settings = SettingsPane()
        self.payload_detail = TerminalPane()
        self.tutorial_detail = TutorialPane()
        self.tutorial_detail.clicked.connect(self.handle_tutorial_click)
        self.panel_highlighters = [
            PanelHighlighter(self.player.body.document()),
            PanelHighlighter(self.target.body.document()),
            PanelHighlighter(self.objective.body.document()),
            PanelHighlighter(self.route.body.document()),
            PanelHighlighter(self.databank.body.document()),
            PanelHighlighter(self.payload_detail.body.document()),
            PanelHighlighter(self.tutorial_detail.body.document()),
            ArchiveHighlighter(self.log_archive.body.document()),
        ]

        self.create_window("terminal", self.shell, "live feed")
        self.create_window("log", self.log_archive, "session log")
        self.create_window("player", self.player, "player")
        self.create_window("target", self.target, "target")
        self.create_window("objective", self.objective, "objective")
        self.create_window("route", self.route, "routeweb")
        self.create_window("databank", self.databank, "databank")
        self.create_window("dev", self.dev_shell, "developer console", show=False)
        self.create_window("settings", self.settings, "settings", show=False)
        self.create_window("payload", self.payload_detail, "payload", show=False)
        self.create_window("tutorial", self.tutorial_detail, "tutorial coach", show=False)

        self.settings.theme_changed.connect(self.change_color_scheme)
        self.settings.font_bias_changed.connect(self.change_font_bias)
        self.settings.reset_requested.connect(self.reset_display_settings)
        self.settings.set_values(self.color_scheme_name, self.font_size_bias)

        for key in ["terminal", "log", "player", "target", "objective", "route", "databank", "dev", "settings", "payload", "tutorial"]:
            button = QPushButton(TASKBAR_LABELS.get(key, key))
            button.setObjectName("dockButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=key: self.toggle_window(name))
            if key == "tutorial":
                button.hide()
            elif key not in {"terminal", "log", "player", "target", "objective", "route", "databank", "settings"}:
                button.hide()
            else:
                self.taskbar_seen_keys.add(key)
            self.dock_layout.addWidget(button)
            self.window_buttons[key] = button

        reset_button = QPushButton("reset layout")
        reset_button.setObjectName("dockUtilityButton")
        reset_button.clicked.connect(self.reset_window_layout)
        self.dock_layout.addWidget(reset_button)

        shadow = QGraphicsDropShadowEffect(self.dock)
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 36))
        self.dock.setGraphicsEffect(shadow)
        self.update_main_menu_state()

    def create_window(self, key: str, content: QWidget, title: str, *, show: bool = True):
        window = FloatingWindow(key, title, content, self.desktop)
        accent = self.get_window_accent(key)
        window.header.accent_dot.setStyleSheet(f"background: {accent}; border-radius: 5px;")
        window.activated.connect(self.activate_window)
        window.hidden_from_ui.connect(lambda _key: self.refresh_taskbar())
        window.shown_from_ui.connect(lambda _key: self.refresh_taskbar())
        self.floating_windows[key] = window
        if show:
            window.show()
            self.taskbar_seen_keys.add(key)
        else:
            window.hide()

    def get_window_accent(self, key: str) -> str:
        accent_map = {
            "terminal": PALETTE["cyan"],
            "log": PALETTE["white"],
            "player": PALETTE["green"],
            "target": PALETTE["yellow"],
            "objective": PALETTE["magenta"],
            "route": PALETTE["accent"],
            "databank": PALETTE["white"],
            "dev": PALETTE["red"],
            "settings": PALETTE["accent"],
            "payload": PALETTE["yellow"],
            "tutorial": PALETTE["magenta"],
        }
        return accent_map.get(key, PALETTE["accent"])

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_layout_done:
            QTimer.singleShot(0, self.reflow_desktop)
            self._initial_layout_done = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._initial_layout_done:
            QTimer.singleShot(0, self.reflow_desktop)

    def reflow_desktop(self):
        self.update_responsive_scale()
        self.layout_boot_menu()
        if self.main_menu_active:
            self.apply_main_menu_visibility()
            self.refresh_taskbar()
            return
        self.reset_window_layout()

    def layout_boot_menu(self):
        rect = self.desktop.rect().adjusted(18, 18, -18, -18)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        width = max(460, min(640, rect.width() // 2))
        height = max(340, min(440, rect.height() // 2))
        x = rect.left() + max(18, (rect.width() - width) // 2)
        y = rect.top() + max(18, (rect.height() - height) // 3)
        self.boot_menu.setGeometry(x, y, width, height)

    def update_main_menu_state(self):
        save_available = os.path.exists(GameState.resolve_save_path())
        self.boot_menu.set_continue_available(save_available)
        if not self.main_menu_pending_choice:
            self.boot_menu.set_busy(False, status=self.boot_menu.status.text())

    def apply_main_menu_visibility(self):
        for window in self.floating_windows.values():
            window.hide()
        self.boot_menu.show()
        self.boot_menu.raise_()
        self.dock.hide()

    def show_main_menu(self):
        self.main_menu_active = True
        self.main_menu_pending_choice = None
        self.update_main_menu_state()
        self.layout_boot_menu()
        self.apply_main_menu_visibility()

    def hide_main_menu(self):
        self.main_menu_active = False
        self.main_menu_pending_choice = None
        self.boot_menu.set_busy(False)
        self.boot_menu.hide()
        self.dock.show()
        self.reset_window_layout()

    def submit_main_menu_choice(self, choice: str):
        self.main_menu_pending_choice = choice
        loading_copy = get_boot_menu_loading_copy(choice)
        self.boot_menu.set_busy(True, subtitle=loading_copy[0], status=loading_copy[1])
        self.layout_boot_menu()
        self.apply_main_menu_visibility()
        self.backend.input_queue.put(choice)

    def reset_window_layout(self):
        if self.main_menu_active:
            self.apply_main_menu_visibility()
            return
        rect = self.desktop.rect().adjusted(18, 18, -18, -18)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        gap = 14
        top_h = max(150, int(rect.height() * 0.19))
        bottom_h = rect.height() - top_h - gap

        side_w = max(390, int(rect.width() * 0.35))
        if rect.width() - side_w - gap < 560:
            side_w = max(340, int(rect.width() * 0.31))
        terminal_w = rect.width() - side_w - gap
        left_top_w = terminal_w
        objective_w = max(250, int(left_top_w * 0.34))
        databank_w = left_top_w - objective_w - gap
        log_h = max(170, int(bottom_h * 0.26))
        terminal_h = max(260, bottom_h - log_h - gap)
        route_h = max(180, int(bottom_h * 0.23))
        target_h = max(250, bottom_h - route_h - gap)
        tutorial_boot_active = self.is_tutorial_boot_active()

        self._place_window("objective", rect.left(), rect.top(), objective_w, top_h, tutorial_boot=tutorial_boot_active)
        self._place_window("databank", rect.left() + objective_w + gap, rect.top(), databank_w, top_h, tutorial_boot=tutorial_boot_active)
        self._place_window("player", rect.left() + terminal_w + gap, rect.top(), side_w, top_h, tutorial_boot=tutorial_boot_active)
        self._place_window("terminal", rect.left(), rect.top() + top_h + gap, terminal_w, terminal_h, tutorial_boot=tutorial_boot_active)
        self._place_window("log", rect.left(), rect.top() + top_h + gap + terminal_h + gap, terminal_w, log_h, tutorial_boot=tutorial_boot_active)
        self._place_window("target", rect.left() + terminal_w + gap, rect.top() + top_h + gap, side_w, target_h, tutorial_boot=tutorial_boot_active)
        self._place_window("route", rect.left() + terminal_w + gap, rect.top() + top_h + gap + target_h + gap, side_w, route_h, tutorial_boot=tutorial_boot_active)

        settings_window = self.floating_windows.get("settings")
        if settings_window:
            settings_rect = QRect(
                rect.left() + terminal_w + gap,
                rect.top() + top_h + gap,
                min(side_w, 360),
                min(bottom_h, 260),
            )
            settings_window._normal_geometry = settings_rect
            settings_window.setGeometry(settings_rect)

        if tutorial_boot_active:
            self.apply_tutorial_boot_visibility()
            self.activate_window("tutorial")
        else:
            self.activate_window("terminal")
        self.refresh_taskbar()

    def _place_window(self, key: str, x: int, y: int, width: int, height: int, *, tutorial_boot: bool = False):
        window = self.floating_windows[key]
        window.is_maximized_window = False
        window._normal_geometry = QRect(x, y, width, height)
        window.setGeometry(x, y, width, height)
        window.header.max_button.setText("[]")
        should_show = not tutorial_boot or key in self.tutorial_boot_revealed
        if should_show:
            window.show()
            window.raise_()
        else:
            window.hide()

    def activate_window(self, key: str):
        for name, window in self.floating_windows.items():
            active = name == key and window.isVisible()
            window.set_active(active)
            if active:
                window.raise_()
        tutorial_window = self.floating_windows.get("tutorial")
        if tutorial_window and tutorial_window.isVisible() and self.backend.objective_is_tutorial and key != "tutorial":
            tutorial_window.raise_()
        self.refresh_taskbar()

    def toggle_window(self, key: str):
        window = self.floating_windows[key]
        if window.isVisible():
            window.hide_window()
        else:
            window.restore_window()
        self.refresh_taskbar()

    def open_tutorial_window(self):
        if not self.backend.objective_is_tutorial:
            return
        self.sync_tutorial_overlay(force_show=True)

    def is_tutorial_boot_active(self) -> bool:
        return self.backend.objective_is_tutorial and self.tutorial_boot_started and not self.tutorial_boot_complete

    def is_tutorial_warmup_gate_active(self) -> bool:
        return (
            self.backend.objective_is_tutorial
            and self.tutorial_boot_complete
            and self.tutorial_warmup_gate_pending
            and not self.backend.current_enemy
        )

    def get_tutorial_boot_steps(self) -> list[dict[str, str | None]]:
        return [
            {
                "focus": step.focus,
                "reveal": step.reveal,
                "title": step.title,
                "body": step.body,
            }
            for step in get_tutorial_boot_steps()
        ]

    def start_tutorial_boot_sequence(self):
        self.tutorial_boot_started = True
        self.tutorial_boot_complete = False
        self.tutorial_boot_step = 0
        self.tutorial_boot_revealed = set()
        self.tutorial_warmup_requested = False
        self.tutorial_warmup_gate_pending = False
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.hide()
        self.refresh_taskbar()

    def finish_tutorial_boot_sequence(self):
        self.tutorial_boot_complete = True
        self.tutorial_boot_revealed = set(self.primary_window_keys)
        self.tutorial_warmup_gate_pending = True
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.show()
                window.raise_()
        self.reset_window_layout()
        self.feed.input_locked = self.is_tutorial_warmup_gate_active()
        if not self.feed.input_locked:
            self.input.setFocus()
            self.feed.move_cursor_to_end()

    def apply_tutorial_boot_visibility(self):
        if not self.is_tutorial_boot_active():
            return
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if not window:
                continue
            if key in self.tutorial_boot_revealed:
                window.show()
            else:
                window.hide()
        tutorial_window = self.floating_windows.get("tutorial")
        if tutorial_window:
            tutorial_window.show()
            tutorial_window.raise_()

    def handle_tutorial_click(self):
        if not self.is_tutorial_boot_active():
            if self.is_tutorial_warmup_gate_active():
                if not self.tutorial_warmup_requested:
                    self.tutorial_warmup_requested = True
                    self.sync_tutorial_overlay(force_show=True)
                    if self.backend.active_prompt:
                        self.backend.input_queue.put("")
                return
            self.open_tutorial_window()
            return

        steps = self.get_tutorial_boot_steps()
        if self.tutorial_boot_step < len(steps) - 1:
            self.tutorial_boot_step += 1
            reveal_key = steps[self.tutorial_boot_step].get("reveal")
            if reveal_key:
                self.tutorial_boot_revealed.add(str(reveal_key))
            self.apply_tutorial_boot_visibility()
            self.sync_tutorial_overlay(force_show=True)
            return

        self.finish_tutorial_boot_sequence()
        self.sync_tutorial_overlay(force_show=True)

    def position_tutorial_window(self, focus_key: str | None):
        window = self.floating_windows["tutorial"]
        rect = self.desktop.rect().adjusted(24, 24, -24, -24)
        if focus_key == "tutorial":
            focus_key = None
        if self.is_tutorial_boot_active():
            width = max(520, min(700, rect.width() // 2))
            height = max(320, min(430, rect.height() // 2))
        else:
            width = max(460, min(620, rect.width() // 2))
            height = max(280, min(380, rect.height() // 2))

        if focus_key and focus_key in self.floating_windows and self.floating_windows[focus_key].isVisible():
            anchor = self.floating_windows[focus_key].geometry()
            candidates = [
                QPoint(anchor.right() + 16, anchor.top()),
                QPoint(anchor.left() - width - 16, anchor.top()),
                QPoint(anchor.left(), anchor.bottom() + 16),
                QPoint(anchor.left(), anchor.top() - height - 16),
            ]
            for point in candidates:
                candidate = QRect(point.x(), point.y(), width, height)
                if rect.contains(candidate):
                    window.setGeometry(candidate)
                    window._normal_geometry = candidate
                    window.clamp_to_desktop()
                    return

        candidate = QRect(
            rect.left() + max(24, (rect.width() - width) // 2),
            rect.top() + 28,
            width,
            height,
        )
        window.setGeometry(candidate)
        window._normal_geometry = candidate
        window.clamp_to_desktop()

    def update_responsive_scale(self):
        height = max(720, self.height())
        width = max(1100, self.width())
        base_ui = max(8, min(13, round(height / 116)))
        base_mono = max(8, min(14, round(min(height / 94, width / 140)) - 1))
        self.current_ui_font_size = max(8, min(20, base_ui + self.font_size_bias))
        self.current_mono_font_size = max(8, min(22, base_mono + self.font_size_bias))

        app = QApplication.instance()
        if not app:
            return

        ui_font = pick_font(
            ["Inter", "Noto Sans", "Ubuntu", "Segoe UI Variable Text", "Segoe UI"],
            point_size=self.current_ui_font_size,
            fixed=False,
        )
        mono_font = pick_font(
            ["JetBrains Mono", "Cascadia Mono", "Fira Code", "DejaVu Sans Mono", "Consolas"],
            point_size=self.current_mono_font_size,
            fixed=True,
        )

        app.setFont(ui_font)
        self.feed.setFont(mono_font)
        self.dev_feed.setFont(mono_font)
        self.brand_label.setFont(ui_font)
        self.session_label.setFont(ui_font)

        for widget in [
            self.player.body,
            self.target.body,
            self.objective.body,
            self.route.body,
            self.databank.body,
            self.payload_detail.body,
            self.tutorial_detail.body,
        ]:
            widget.setFont(mono_font)

        for widget in [
            self.settings,
            self.settings.title,
            self.settings.note,
            self.settings.theme_combo,
            self.settings.font_bias_spin,
            self.settings.reset_button,
        ]:
            widget.setFont(ui_font)

        for chip in [self.day_chip, self.wallet_chip, self.trace_chip, self.sweep_chip, self.status_chip, self.clock_chip]:
            chip.label.setFont(ui_font)
            chip.value.setFont(ui_font)

        for window in self.floating_windows.values():
            window.header.title_label.setFont(ui_font)
            for button in [window.header.min_button, window.header.max_button, window.header.close_button]:
                button.setFont(ui_font)

    def change_color_scheme(self, scheme_name: str):
        if scheme_name not in COLOR_SCHEMES:
            return
        self.color_scheme_name = scheme_name
        PALETTE.clear()
        PALETTE.update(BASE_PALETTE)
        PALETTE.update(COLOR_SCHEMES[scheme_name])
        self.apply_theme()
        self.desktop.update()
        self.refresh_all()

    def change_font_bias(self, bias: int):
        self.font_size_bias = bias
        self.apply_theme()
        self.refresh_all()

    def reset_display_settings(self):
        self.color_scheme_name = "Midnight"
        self.font_size_bias = 0
        self.settings.set_values(self.color_scheme_name, self.font_size_bias)
        PALETTE.clear()
        PALETTE.update(BASE_PALETTE)
        self.apply_theme()
        self.desktop.update()
        self.refresh_all()

    def apply_theme(self):
        self.update_responsive_scale()
        self.feed_highlighter.refresh_palette()
        self.dev_feed_highlighter.refresh_palette()
        for highlighter in self.panel_highlighters:
            highlighter.refresh_palette()
        for key, window in self.floating_windows.items():
            window.header.accent_dot.setStyleSheet(f"background: {self.get_window_accent(key)}; border-radius: 5px;")
            repolish(window)

        self.setStyleSheet(
            f"""
            QWidget#root {{
                background: {PALETTE["desktop_top"]};
                color: {PALETTE["text"]};
            }}
            QFrame#topBar {{
                background: rgba(14, 18, 27, 0.985);
                border-bottom: 1px solid {PALETTE["panel_border"]};
            }}
            QFrame#bootMenuOverlay {{
                background: rgba(12, 17, 26, 0.97);
                border: 1px solid {PALETTE["panel_border_active"]};
                border-radius: 14px;
            }}
            QLabel#bootMenuTitle {{
                color: {PALETTE["white"]};
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QLabel#bootMenuSubtitle {{
                color: {PALETTE["text"]};
            }}
            QLabel#bootMenuStatus {{
                color: {PALETTE["cyan"]};
            }}
            QLabel#bootMenuFooter {{
                color: {PALETTE["muted"]};
            }}
            QPushButton#bootMenuButton {{
                background: {PALETTE["terminal_alt"]};
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 9px;
                color: {PALETTE["text"]};
                padding: 10px 14px;
                text-align: left;
            }}
            QPushButton#bootMenuButton:hover {{
                border-color: {PALETTE["panel_border_active"]};
                background: {PALETTE["accent_soft"]};
            }}
            QPushButton#bootMenuButton:disabled {{
                color: {PALETTE["muted"]};
                border-color: {PALETTE["panel_border"]};
                background: rgba(16, 22, 33, 0.85);
            }}
            QPushButton#bootMenuButton[role="danger"] {{
                color: {PALETTE["red"]};
            }}
            QLabel#brandLabel {{
                color: {PALETTE["white"]};
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QLabel#sessionLabel {{
                color: {PALETTE["muted"]};
            }}
            QFrame#statChip {{
                background: rgba(15, 20, 30, 0.94);
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 9px;
            }}
            QFrame#statChip[kind="positive"] {{
                border-color: #27523b;
                background: rgba(16, 33, 27, 0.95);
            }}
            QFrame#statChip[kind="warning"] {{
                border-color: #5d4721;
                background: rgba(41, 30, 12, 0.95);
            }}
            QFrame#statChip[kind="danger"] {{
                border-color: #5b2832;
                background: rgba(44, 18, 25, 0.95);
            }}
            QFrame#statChip[kind="accent"] {{
                border-color: #284777;
                background: rgba(16, 28, 47, 0.95);
            }}
            QLabel#statChipLabel {{
                color: {PALETTE["muted"]};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.6px;
            }}
            QLabel#statChipValue {{
                color: {PALETTE["text"]};
                font-weight: 700;
            }}
            QWidget#desktopCanvas {{
                background: transparent;
            }}
            QFrame#dock {{
                background: rgba(10, 14, 22, 0.72);
                border: 1px solid rgba(58, 70, 92, 0.7);
                border-radius: 9px;
            }}
            QPushButton#dockButton, QPushButton#dockUtilityButton {{
                border: 1px solid transparent;
                background: transparent;
                color: {PALETTE["muted"]};
                padding: 4px 12px;
                border-radius: 7px;
                text-align: center;
            }}
            QPushButton#dockButton {{
                min-width: 72px;
            }}
            QPushButton#dockButton:checked {{
                background: rgba(26, 37, 58, 0.95);
                border-color: rgba(92, 140, 255, 0.75);
                color: {PALETTE["white"]};
            }}
            QPushButton#dockButton[active="true"] {{
                background: rgba(26, 37, 58, 0.95);
                border-color: rgba(92, 140, 255, 0.75);
                color: {PALETTE["white"]};
                font-weight: 700;
            }}
            QPushButton#dockButton:hover, QPushButton#dockUtilityButton:hover {{
                border-color: rgba(95, 140, 255, 0.45);
                background: rgba(20, 28, 42, 0.92);
                color: {PALETTE["text"]};
            }}
            QFrame#settingsPane {{
                background: transparent;
            }}
            QLabel#settingsTitle {{
                color: {PALETTE["white"]};
                font-weight: 700;
            }}
            QLabel#settingsNote {{
                color: {PALETTE["muted"]};
            }}
            QComboBox#settingsCombo, QSpinBox#settingsSpin {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 7px;
                background: {PALETTE["terminal_alt"]};
                color: {PALETTE["text"]};
                padding: 5px 8px;
                min-height: 30px;
            }}
            QComboBox#settingsCombo:hover, QSpinBox#settingsSpin:hover {{
                border-color: {PALETTE["panel_border_active"]};
            }}
            QPushButton#settingsReset {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 7px;
                background: {PALETTE["terminal_alt"]};
                color: {PALETTE["text"]};
                padding: 6px 10px;
            }}
            QPushButton#settingsReset:hover {{
                border-color: {PALETTE["panel_border_active"]};
                background: {PALETTE["accent_soft"]};
            }}
            QFrame#floatingWindow {{
                background: {PALETTE["panel"]};
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 8px;
            }}
            QFrame#floatingWindow[active="true"] {{
                border-color: {PALETTE["panel_border_active"]};
            }}
            QFrame#floatingWindow[guided="true"] {{
                border: 2px solid {PALETTE["yellow"]};
            }}
            QFrame#windowHeader {{
                background: {PALETTE["header"]};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid {PALETTE["panel_border"]};
            }}
            QFrame#floatingWindow[active="true"] QFrame#windowHeader {{
                background: {PALETTE["header_active"]};
            }}
            QFrame#floatingWindow[guided="true"] QFrame#windowHeader {{
                background: #3b3013;
                border-bottom: 1px solid {PALETTE["yellow"]};
            }}
            QLabel#windowAccentDot {{
                border-radius: 5px;
                background: {PALETTE["accent"]};
            }}
            QLabel#windowTitle {{
                color: {PALETTE["white"]};
                font-weight: 700;
            }}
            QPushButton#windowControl {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 9px;
                color: {PALETTE["muted"]};
            }}
            QPushButton#windowControl:hover {{
                border-color: {PALETTE["panel_border"]};
                background: #1f2737;
                color: {PALETTE["white"]};
            }}
            QPushButton#windowControl[role="close"]:hover {{
                border-color: #6c3140;
                background: #3a1821;
                color: #ffd7d3;
            }}
            QFrame#windowContentShell {{
                background: {PALETTE["panel"]};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QFrame#paneSurface, QFrame#terminalSurface {{
                background: transparent;
                border: none;
            }}
            QFrame#terminalViewport {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 8px;
                background: {PALETTE["terminal_alt"]};
            }}
            QPlainTextEdit#paneBody, QPlainTextEdit#feed {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 8px;
                background: {PALETTE["terminal"]};
                color: {PALETTE["text"]};
                padding: 7px;
                selection-background-color: {PALETTE["accent_soft"]};
            }}
            QPlainTextEdit#feed {{
                background: transparent;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #263246;
                border-radius: 6px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #35507a;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar:horizontal, QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: transparent;
                border: none;
                width: 0px;
                height: 0px;
            }}
            """
        )
        self.desktop.update()

    def install_click_focus_proxy(self):
        widgets = [
            self,
            self.centralWidget(),
            self.top_bar,
            self.dock,
            self.desktop,
            self.shell,
            self.shell.viewport,
            self.feed,
            self.log_archive,
            self.log_archive.body,
            self.player,
            self.player.body,
            self.target,
            self.target.body,
            self.objective,
            self.objective.body,
            self.route,
            self.route.body,
            self.databank,
            self.databank.body,
            self.dev_shell,
            self.dev_shell.viewport,
            self.dev_feed,
            self.payload_detail,
            self.payload_detail.body,
        ]
        for widget in widgets:
            widget.installEventFilter(self)

        for window in self.floating_windows.values():
            window.installEventFilter(self)
            window.header.installEventFilter(self)
            window.content_shell.installEventFilter(self)

    @staticmethod
    def widget_is_within(obj, ancestor: QWidget) -> bool:
        widget = obj if isinstance(obj, QWidget) else None
        while widget is not None:
            if widget is ancestor:
                return True
            widget = widget.parentWidget()
        return False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and not self.main_menu_active:
            if self.dev_feed.prompt_active and self.widget_is_within(obj, self.dev_shell):
                if obj is not self.dev_input:
                    self.dev_input.setFocus()
                    self.dev_feed.move_cursor_to_end()
            elif obj is not self.input and self.feed.prompt_active:
                self.input.setFocus()
                self.feed.move_cursor_to_end()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self.backend.running = False
        if self.backend.game_thread and self.backend.game_thread.is_alive() and self.backend.active_prompt:
            self.backend.input_queue.put("")
        super().closeEvent(event)

    def submit_command(self, command: str):
        if self.is_tutorial_boot_active() or self.is_tutorial_warmup_gate_active():
            self.open_tutorial_window()
            return
        self.backend.current_input = command
        self.backend.submit_current_input()

    def refresh_from_backend(self):
        bootloader_prompt = self.backend.active_prompt.strip().lower().startswith("select an option:")
        if bootloader_prompt and not self.main_menu_active and not self.main_menu_pending_choice:
            self.show_main_menu()

        self.refresh_log()
        self.refresh_top_bar()
        self.refresh_windows()
        self.refresh_dev_console()

        if not self.main_menu_active and self.backend.consume_dev_console_request():
            self.open_dev_console()

        if self.main_menu_active and self.main_menu_pending_choice:
            if self.main_menu_pending_choice == "1":
                if self.backend.objective_is_tutorial and self.tutorial_boot_started:
                    self.hide_main_menu()
            elif self.backend.state is not None and not self.backend.objective_is_tutorial and not bootloader_prompt:
                self.hide_main_menu()

        self.refresh_prompt_bar()
        self.refresh_taskbar()

        if self.backend.game_thread and not self.backend.game_thread.is_alive() and not self.backend.running:
            self.close()

    def refresh_all(self):
        self.refresh_top_bar()
        self.refresh_windows()
        self.refresh_dev_console()
        self.refresh_prompt_bar()
        self.refresh_taskbar()

    def refresh_log(self):
        with self.backend.io_lock:
            snapshot = list(self.backend.log_lines)

        if self.feed.set_history(snapshot):
            self.feed_highlighter.set_line_tones([tone for _line, tone in snapshot])
            self._last_log_snapshot = snapshot

    def refresh_top_bar(self):
        if self.main_menu_active:
            self.brand_label.setText("terminal rogue")
            self.session_label.setText("boot menu // select a session mode")
            self.day_chip.set_value("--")
            self.day_chip.set_kind("accent")
            self.wallet_chip.set_value("--")
            self.wallet_chip.set_kind("accent")
            self.trace_chip.set_value("--")
            self.trace_chip.set_kind("accent")
            self.sweep_chip.set_value("--")
            self.sweep_chip.set_kind("accent")
            self.status_chip.set_value("boot menu")
            self.status_chip.set_kind("accent")
            self.clock_chip.set_value(datetime.now().strftime("%H:%M"))
            self.clock_chip.set_kind("accent")
            return

        identity = self.backend.get_terminal_identity()
        shell_path = self.backend.get_shell_cwd()
        day = self.backend.state.day if self.backend.state else "--"
        crypto = self.backend.state.player_crypto if self.backend.state else 0
        trace = self.backend.state.trace_level if self.backend.state else 0
        sweep_value = (
            f"{self.backend.route_sweep_level}/{self.backend.route_sweep_max}"
            if self.backend.route_sweep_max
            else "--"
        )
        active = self.backend.map_status or "idle shell"
        clock_text = datetime.now().strftime("%H:%M")

        self.brand_label.setText("terminal rogue")
        self.session_label.setText(f"{identity}:{shell_path}")

        self.day_chip.set_value(str(day))
        self.day_chip.set_kind("accent")
        self.wallet_chip.set_value(f"{crypto}c")
        self.wallet_chip.set_kind("positive")
        self.trace_chip.set_value(str(trace))
        self.trace_chip.set_kind(self.kind_for_level(trace, warn=6, danger=10))
        self.sweep_chip.set_value(sweep_value)
        self.sweep_chip.set_kind(self.kind_for_level(self.backend.route_sweep_level, warn=3, danger=6))
        self.status_chip.set_value(active)
        self.status_chip.set_kind("accent")
        self.clock_chip.set_value(clock_text)
        self.clock_chip.set_kind("accent")

    @staticmethod
    def kind_for_level(value: int, *, warn: int, danger: int) -> str:
        if value >= danger:
            return "danger"
        if value >= warn:
            return "warning"
        return "accent"

    def refresh_windows(self):
        self.set_window_title("terminal", self.backend.format_pane_title(self.backend.get_shell_cwd()))
        self.set_window_title("log", self.backend.format_pane_title("~/var/log/session.log"))
        self.set_window_title("player", self.backend.format_pane_title("~/proc/player"))
        self.set_window_title("target", self.backend.format_pane_title("~/proc/target"))
        self.set_window_title("objective", self.backend.format_pane_title("~/proc/objective"))
        self.set_window_title("settings", self.backend.format_pane_title("~/usr/share/settings"))
        self.set_window_title("dev", self.backend.format_pane_title("~/usr/local/devshell"))
        self.set_window_title("route", self.backend.format_pane_title("~/net/routeweb"))
        self.set_window_title("databank", self.backend.format_pane_title("~/usr/share/databank"))

        self.player.set_text(self.build_player_text())
        self.target.set_text(self.build_target_text())
        self.objective.set_text(self.build_objective_text())
        self.route.set_text(self.build_route_text())
        self.log_archive.set_text(self.build_log_text())
        self.databank.set_text(self.build_databank_text())
        self.sync_tutorial_overlay()

    def set_window_title(self, key: str, title: str):
        window = self.floating_windows.get(key)
        if window:
            window.set_title(title)

    def lookup_databank_entry(self, raw_line: str):
        line = raw_line.strip()
        if not line or line in {"TOOLS", "FLAGS", "ITEMS", "TARGETS"}:
            return None
        if (
            line.upper().startswith("NAME")
            or line.upper().startswith("FLAG")
            or line.upper().startswith("ITEM")
            or line.upper().startswith("TARGET")
        ):
            return None

        token = line.split()[0]
        if token.upper() in {"OS", "SEC", "NET", "MEM", "STO"}:
            return {"kind": "target", "id": token.upper(), "title": token.upper(), "data": {}}
        arsenal = getattr(self.backend, "arsenal", None)
        player = getattr(self.backend, "player", None)
        if arsenal and token in arsenal.scripts and (not player or player.owns_script(token)):
            data = arsenal.scripts[token]
            return {"kind": "script", "id": token, "title": token, "data": data}
        if arsenal and token in arsenal.flags and (not player or player.owns_flag(token)):
            data = arsenal.flags[token]
            return {"kind": "flag", "id": token, "title": token, "data": data}
        if token in self.backend.item_library and (not player or player.get_consumable_count(token) > 0):
            data = self.backend.item_library.get(token, {})
            return {"kind": "item", "id": token, "title": data.get("name", token), "data": data}
        return None

    def open_databank_entry(self, entry):
        window = self.floating_windows["payload"]
        title = self.backend.format_pane_title(f"~/usr/share/{entry['id']}")
        window.set_title(title)
        self.payload_detail.set_text(self.build_databank_entry_text(entry))

        rect = self.desktop.rect().adjusted(28, 28, -28, -28)
        if window.isVisible():
            width = max(window.width(), window.minimumWidth())
            height = max(window.height(), window.minimumHeight())
        else:
            width = max(360, min(470, rect.width() // 3))
            height = max(270, min(380, rect.height() // 2))

        cursor_pos = self.desktop.mapFromGlobal(QCursor.pos())
        offset = QPoint(16, 16)
        x = cursor_pos.x() + offset.x()
        y = cursor_pos.y() + offset.y()

        if x + width > rect.right():
            x = cursor_pos.x() - width - offset.x()
        if y + height > rect.bottom():
            y = cursor_pos.y() - height - offset.y()

        x = max(rect.left(), min(x, rect.right() - width))
        y = max(rect.top(), min(y, rect.bottom() - height))

        window.is_maximized_window = False
        window.header.max_button.setText("[]")
        window.setGeometry(x, y, width, height)
        window._normal_geometry = window.geometry()

        if not window.isVisible():
            window.show()

        window.clamp_to_desktop()
        window.raise_()
        self.activate_window("payload")

    @staticmethod
    def _clip_lines(snapshot: list[tuple[str, str]], limit: int = 1600) -> list[tuple[str, str]]:
        return snapshot[-limit:] if len(snapshot) > limit else snapshot

    def get_dev_prompt(self) -> str:
        return "root@ops-dev:~/sandbox# "

    def append_dev_output(self, text: str, tone: str = "text"):
        normalized = text.replace("\r", "")
        parts = normalized.split("\n")
        if parts and parts[-1] == "":
            parts = parts[:-1]
        if not parts:
            parts = [""]
        for part in parts:
            self.dev_log_lines.append((part, tone))
        self.dev_log_lines = self._clip_lines(self.dev_log_lines)

    def clear_dev_console_output(self):
        self.dev_log_lines = []

    def seed_dev_console(self):
        if self.dev_bootstrapped:
            return
        for line, tone in dev_console_banner_lines():
            self.append_dev_output(line, tone)
        self.dev_bootstrapped = True

    def refresh_dev_console(self):
        if self.dev_feed.set_history(self.dev_log_lines):
            self.dev_feed_highlighter.set_line_tones([tone for _line, tone in self.dev_log_lines])
            self._dev_last_snapshot = list(self.dev_log_lines)
        prompt_active = not self.main_menu_active
        prompt = self.get_dev_prompt() if prompt_active else ""
        self.dev_feed.input_locked = self.main_menu_active
        self.dev_feed.set_prompt_state(prompt, prompt_active)
        self.dev_feed_highlighter.set_live_prompt(len(self.dev_feed.history_lines) if prompt_active else -1, prompt if prompt_active else "")

    def open_dev_console(self):
        if self.main_menu_active:
            return
        self.seed_dev_console()
        self.refresh_dev_console()
        window = self.floating_windows["dev"]
        rect = self.desktop.rect().adjusted(32, 32, -32, -32)
        width = max(620, min(940, int(rect.width() * 0.58)))
        height = max(420, min(680, int(rect.height() * 0.66)))
        x = rect.left() + max(24, (rect.width() - width) // 2)
        y = rect.top() + max(24, (rect.height() - height) // 4)
        if not window.isVisible():
            window.setGeometry(x, y, width, height)
            window._normal_geometry = window.geometry()
            window.show()
        self.taskbar_seen_keys.add("dev")
        window.clamp_to_desktop()
        window.raise_()
        self.activate_window("dev")
        self.dev_input.setFocus()
        self.dev_feed.move_cursor_to_end()
        self.refresh_taskbar()

    def submit_dev_command(self, command: str):
        if self.main_menu_active:
            return
        self.seed_dev_console()
        prompt = self.get_dev_prompt()
        echo_line = f"{prompt}{command}".rstrip()
        self.append_dev_output(echo_line if echo_line else prompt.rstrip(), "green")
        stripped = command.strip()
        if stripped:
            self.dev_command_history.append(stripped)
            if len(self.dev_command_history) > 240:
                self.dev_command_history = self.dev_command_history[-240:]
        with self.backend.io_lock:
            self.handle_dev_command(command)
        self.refresh_dev_console()
        if self.floating_windows["dev"].isVisible():
            self.dev_input.setFocus()
            self.dev_feed.move_cursor_to_end()

    def handle_dev_command(self, command: str):
        stripped = command.strip()
        if not stripped:
            return

        try:
            parts = shlex.split(stripped)
        except ValueError as exc:
            self.append_dev_output(f"parse error: {exc}", "red")
            return

        name = parts[0].lower()
        args = parts[1:]

        if name in {"clear", "cls"}:
            self.clear_dev_console_output()
            return

        if name in {"close", "exit", "quit"}:
            self.floating_windows["dev"].hide_window()
            return

        if name in {"help", "?"}:
            self.append_dev_output(self.build_dev_help_text(), "cyan")
            return

        if name == "status":
            self.append_dev_output(self.build_dev_status_text(), "white")
            return

        if name == "save":
            if not self.backend.state or not self.backend.player:
                self.append_dev_output("save failed: no live session state loaded.", "red")
                return
            try:
                GameState.save_session(self.backend.state, self.backend.player)
            except Exception as exc:
                self.append_dev_output(f"save failed: {exc}", "red")
                return
            self.append_dev_output("session snapshot written to disk.", "green")
            return

        if name == "dump" or name in {
            "player",
            "target",
            "objective",
            "route",
            "world",
            "databank",
            "log",
            "state",
            "contracts",
            "history",
        }:
            topic = args[0] if name == "dump" and args else name
            if not topic:
                self.append_dev_output("usage: dump <player|target|objective|route|databank|log|state|contracts|history>", "red")
                return
            text = self.build_dev_dump_text(topic.lower())
            if text is None:
                self.append_dev_output(f"unknown dump target: {topic}", "red")
            else:
                self.append_dev_output(text, "white")
            return

        if name == "set":
            self.handle_dev_set_command(args)
            return

        if name == "hp":
            self.handle_dev_hp_command(args)
            return

        if name in {"grant", "revoke"}:
            self.handle_dev_grant_revoke_command(name, args)
            return

        if name in {"give", "take"}:
            self.handle_dev_item_command(name, args)
            return

        if name in {"reveal", "conceal"}:
            self.handle_dev_reveal_command(name, args)
            return

        if name == "route":
            self.handle_dev_route_command(args)
            return

        if name == "window":
            self.handle_dev_window_command(args)
            return

        if name == "layout":
            self.handle_dev_layout_command(args)
            return

        self.append_dev_output(f"unknown command: {name}", "red")

    def build_dev_help_text(self) -> str:
        return "\n".join(
            [
                "developer console // commands",
                "",
                "help",
                "status",
                "dump player|target|objective|route|databank|log|state|contracts|history",
                "set day|crypto|trace|ram|maxram <value>",
                "hp player|target <OS|SEC|NET|MEM|STO> <current> [max]",
                "grant script|flag <id>",
                "revoke script|flag <id>",
                "give item <id> [qty]",
                "take item <id> [qty]",
                "reveal target surface|identity|weapon|telemetry|intent|weakness|all",
                "conceal target surface|identity|weapon|telemetry|intent|weakness|all",
                "route status",
                "route clear|reopen|activate <ip|active>",
                "window list",
                "window open|close|focus <name>",
                "layout reset",
                "save",
                "clear / cls",
                "close",
            ]
        )

    def build_dev_status_text(self) -> str:
        lines = ["runtime status", ""]
        state = self.backend.state
        player = self.backend.player
        enemy = self.backend.current_enemy

        if state:
            lines.append(f"day {state.day}  wallet {state.player_crypto}c  trace {state.trace_level}")
        else:
            lines.append("no live session state")

        if player:
            lines.append(
                f"player {player.handle}  ram {player.current_ram}/{player.get_effective_max_ram()}  "
                f"scripts {len(player.owned_scripts)}  flags {len(player.owned_flags)}"
            )
        else:
            lines.append("player offline")

        if enemy:
            lines.append(
                f"target {enemy.get_visible_name()}  "
                f"os {enemy.subsystems['OS'].current_hp}/{enemy.subsystems['OS'].max_hp}  "
                f"entry {enemy.get_recon_alert_text().lower()}"
            )
        else:
            lines.append("target none")

        if self.backend.map_world:
            active_node = None
            if self.backend.map_active is not None and 0 <= self.backend.map_active < len(self.backend.map_world.nodes):
                active_node = self.backend.map_world.nodes[self.backend.map_active].ip_address
            lines.append(
                f"route {self.backend.map_world.subnet_name}  active {active_node or 'none'}  "
                f"cleared {len(self.backend.map_cleared)}"
            )
        else:
            lines.append("route mesh offline")

        return "\n".join(lines)

    def build_dev_dump_text(self, topic: str) -> str | None:
        mapping = {
            "player": self.backend.build_shell_player_text,
            "target": self.backend.build_shell_target_text,
            "objective": self.backend.build_shell_objective_text,
            "route": self.build_route_map_text,
            "world": self.build_route_map_text,
            "databank": self.build_databank_text,
            "log": self.backend.build_shell_session_log_text,
            "state": self.build_dev_state_text,
            "contracts": self.build_dev_contract_text,
            "history": self.build_dev_history_text,
        }
        builder = mapping.get(topic)
        return builder() if builder else None

    def build_dev_state_text(self) -> str:
        state = self.backend.state
        if not state:
            return "state unavailable"
        lines = [
            "session state",
            "",
            f"day             {state.day}",
            f"wallet          {state.player_crypto}c",
            f"trace           {state.trace_level}",
            f"game over       {state.game_over}",
            f"prologue done   {state.prologue_complete}",
            f"origin          {state.origin_story}",
            f"seed            {state.run_seed}",
            f"contracts       {len(state.current_contracts)} active / {len(state.contract_history)} archived",
        ]
        return "\n".join(lines)

    def build_dev_contract_text(self) -> str:
        state = self.backend.state
        if not state or not state.current_contracts:
            return "contracts // none active"
        lines = ["contracts", ""]
        for contract in state.current_contracts:
            status = self.backend.get_contract_status(contract)
            lines.append(f"{status:<9} {contract['target_ip']}  {contract['subject']}")
        return "\n".join(lines)

    def build_dev_history_text(self) -> str:
        if not self.dev_command_history:
            return "developer console history is empty"
        width = len(str(len(self.dev_command_history)))
        return "\n".join(f"{idx:>{width}}  {value}" for idx, value in enumerate(self.dev_command_history, start=1))

    def normalize_runtime_state(self):
        player = self.backend.player
        if player:
            for subsystem in player.subsystems.values():
                subsystem.max_hp = max(1, int(subsystem.max_hp))
                subsystem.current_hp = max(0, min(int(subsystem.current_hp), subsystem.max_hp))
                subsystem.is_destroyed = subsystem.current_hp <= 0
            player.current_ram = max(0, min(int(player.current_ram), player.get_effective_max_ram()))

        enemy = self.backend.current_enemy
        if enemy:
            for subsystem in enemy.subsystems.values():
                subsystem.max_hp = max(1, int(subsystem.max_hp))
                subsystem.current_hp = max(0, min(int(subsystem.current_hp), subsystem.max_hp))
                subsystem.is_destroyed = subsystem.current_hp <= 0

        if self.backend.arsenal:
            self.backend.update_arsenal_display(self.backend.arsenal)

    @staticmethod
    def resolve_subsystem_key(raw: str) -> str:
        key = raw.strip().upper()
        if key not in {"OS", "SEC", "NET", "MEM", "STO"}:
            raise ValueError("subsystem must be one of OS, SEC, NET, MEM, STO")
        return key

    def handle_dev_set_command(self, args: list[str]):
        if len(args) < 2:
            self.append_dev_output("usage: set day|crypto|trace|ram|maxram <value>", "red")
            return
        field = args[0].lower()
        try:
            value = int(args[1])
        except ValueError:
            self.append_dev_output("set value must be an integer.", "red")
            return

        if field in {"day", "crypto", "trace"} and not self.backend.state:
            self.append_dev_output("no live session state to edit.", "red")
            return
        if field in {"ram", "maxram"} and not self.backend.player:
            self.append_dev_output("no player rig loaded.", "red")
            return

        if field == "day":
            self.backend.state.day = max(1, value)
            unlocked = self.backend.apply_day_unlocks(announce=False)
            self.append_dev_output(f"day set to {self.backend.state.day}.", "green")
            for line in unlocked:
                self.append_dev_output(line, "cyan")
        elif field == "crypto":
            self.backend.state.player_crypto = max(0, value)
            self.append_dev_output(f"wallet set to {self.backend.state.player_crypto}c.", "green")
        elif field == "trace":
            self.backend.state.trace_level = max(0, value)
            self.append_dev_output(f"trace set to {self.backend.state.trace_level}.", "green")
        elif field == "ram":
            self.backend.player.current_ram = max(0, value)
            self.normalize_runtime_state()
            self.append_dev_output(f"current RAM set to {self.backend.player.current_ram}.", "green")
        elif field == "maxram":
            self.backend.player.max_ram = max(1, value)
            self.normalize_runtime_state()
            self.append_dev_output(f"base max RAM set to {self.backend.player.max_ram}.", "green")
        else:
            self.append_dev_output(f"unknown set field: {field}", "red")
            return

        self.normalize_runtime_state()

    def handle_dev_hp_command(self, args: list[str]):
        if len(args) < 3:
            self.append_dev_output("usage: hp player|target <OS|SEC|NET|MEM|STO> <current> [max]", "red")
            return
        scope = args[0].lower()
        try:
            subsystem_key = self.resolve_subsystem_key(args[1])
            current_value = int(args[2])
            max_value = int(args[3]) if len(args) > 3 else None
        except ValueError as exc:
            self.append_dev_output(str(exc), "red")
            return

        entity = self.backend.player if scope == "player" else self.backend.current_enemy if scope == "target" else None
        if entity is None:
            self.append_dev_output(f"{scope} entity is not available.", "red")
            return

        subsystem = entity.subsystems[subsystem_key]
        if max_value is not None:
            subsystem.max_hp = max(1, max_value)
        subsystem.current_hp = max(0, min(current_value, subsystem.max_hp))
        subsystem.is_destroyed = subsystem.current_hp <= 0
        self.normalize_runtime_state()
        self.append_dev_output(
            f"{scope} {subsystem_key} set to {subsystem.current_hp}/{subsystem.max_hp}.",
            "green",
        )

    def handle_dev_grant_revoke_command(self, action: str, args: list[str]):
        if len(args) < 2:
            self.append_dev_output(f"usage: {action} script|flag <id>", "red")
            return
        if not self.backend.player or not self.backend.arsenal:
            self.append_dev_output("no live player toolkit loaded.", "red")
            return
        kind = args[0].lower()
        payload_id = args[1]

        if kind == "script":
            if payload_id not in self.backend.arsenal.scripts:
                self.append_dev_output(f"unknown script: {payload_id}", "red")
                return
            if action == "grant":
                self.backend.player.grant_script(payload_id)
            else:
                self.backend.player.owned_scripts.discard(payload_id)
        elif kind == "flag":
            if payload_id not in self.backend.arsenal.flags:
                self.append_dev_output(f"unknown flag: {payload_id}", "red")
                return
            if action == "grant":
                self.backend.player.grant_flag(payload_id)
            else:
                self.backend.player.owned_flags.discard(payload_id)
        else:
            self.append_dev_output(f"unknown toolkit kind: {kind}", "red")
            return

        self.normalize_runtime_state()
        self.append_dev_output(f"{action}ed {kind} {payload_id}.", "green")

    def handle_dev_item_command(self, action: str, args: list[str]):
        if not args:
            self.append_dev_output(f"usage: {action} item <id> [qty]", "red")
            return
        if not self.backend.player:
            self.append_dev_output("no player rig loaded.", "red")
            return
        if args[0].lower() == "item":
            args = args[1:]
        if not args:
            self.append_dev_output(f"usage: {action} item <id> [qty]", "red")
            return
        item_id = args[0].lower()
        qty = 1
        if len(args) > 1:
            try:
                qty = max(1, int(args[1]))
            except ValueError:
                self.append_dev_output("item quantity must be an integer.", "red")
                return

        if item_id not in self.backend.item_library:
            self.append_dev_output(f"unknown item: {item_id}", "red")
            return

        if action == "give":
            self.backend.player.grant_consumable(item_id, qty)
            self.append_dev_output(f"added {qty}x {item_id}.", "green")
        else:
            current = self.backend.player.get_consumable_count(item_id)
            if current <= 0:
                self.append_dev_output(f"no {item_id} in inventory.", "red")
                return
            remaining = max(0, current - qty)
            if remaining <= 0:
                self.backend.player.consumables.pop(item_id, None)
            else:
                self.backend.player.consumables[item_id] = remaining
            self.append_dev_output(f"removed {min(qty, current)}x {item_id}.", "green")

        self.normalize_runtime_state()

    def handle_dev_reveal_command(self, action: str, args: list[str]):
        if len(args) < 2 or args[0].lower() != "target":
            self.append_dev_output(f"usage: {action} target surface|identity|weapon|telemetry|intent|weakness|all", "red")
            return
        enemy = self.backend.current_enemy
        if not enemy:
            self.append_dev_output("no live target to edit.", "red")
            return
        field = args[1].lower()
        enable = action == "reveal"

        if field == "all":
            if enable:
                enemy.reveal_surface()
                enemy.telemetry_targets = set(enemy.subsystems.keys())
                enemy.intent_revealed = True
                enemy.weakness_revealed = True
            else:
                enemy.identity_revealed = False
                enemy.weapon_revealed = False
                enemy.topology_revealed = False
                enemy.telemetry_targets = set()
                enemy.intent_revealed = False
                enemy.weakness_revealed = False
        elif field in {"surface", "topology"}:
            if enable:
                enemy.topology_revealed = True
            else:
                enemy.topology_revealed = False
                enemy.telemetry_targets = set()
        elif field == "identity":
            enemy.identity_revealed = enable
        elif field == "weapon":
            enemy.weapon_revealed = enable
        elif field == "telemetry":
            enemy.telemetry_targets = set(enemy.subsystems.keys()) if enable else set()
        elif field == "intent":
            enemy.intent_revealed = enable
        elif field == "weakness":
            enemy.weakness_revealed = enable
        else:
            self.append_dev_output(f"unknown reveal field: {field}", "red")
            return

        self.normalize_runtime_state()
        self.append_dev_output(f"{action}d target {field}.", "green")

    def find_world_node(self, token: str):
        world = self.backend.map_world
        if not world:
            return None, None
        raw = token.strip().lower()
        if raw == "active":
            index = self.backend.map_active
            if index is None:
                return None, None
            return index, world.nodes[index]
        for index, node in enumerate(world.nodes):
            if node.ip_address.lower() == raw:
                return index, node
        return None, None

    def handle_dev_route_command(self, args: list[str]):
        world = self.backend.map_world
        if not world:
            self.append_dev_output("no route mesh is currently loaded.", "red")
            return
        if not args or args[0].lower() == "status":
            self.append_dev_output(self.build_route_map_text(), "white")
            return

        action = args[0].lower()
        if len(args) < 2:
            self.append_dev_output("usage: route clear|reopen|activate <ip|active>", "red")
            return

        node_index, node = self.find_world_node(args[1])
        if node is None:
            self.append_dev_output(f"route target not found: {args[1]}", "red")
            return

        if action == "clear":
            self.backend.map_cleared.add(node_index)
            self.append_dev_output(f"marked {node.ip_address} as cleared.", "green")
        elif action == "reopen":
            self.backend.map_cleared.discard(node_index)
            self.append_dev_output(f"reopened {node.ip_address}.", "green")
        elif action == "activate":
            self.backend.set_network_world(world, self.backend.map_cleared, node_index, self.backend.map_status)
            self.append_dev_output(f"active route focus moved to {node.ip_address}.", "green")
        else:
            self.append_dev_output(f"unknown route action: {action}", "red")
            return

        self.normalize_runtime_state()

    def resolve_dev_window_key(self, raw: str) -> str | None:
        token = raw.strip().lower()
        alias_map = {
            "term": "terminal",
            "terminal": "terminal",
            "shell": "terminal",
            "feed": "terminal",
            "log": "log",
            "archive": "log",
            "player": "player",
            "target": "target",
            "objective": "objective",
            "route": "route",
            "routeweb": "route",
            "databank": "databank",
            "db": "databank",
            "settings": "settings",
            "payload": "payload",
            "tutorial": "tutorial",
            "coach": "tutorial",
            "dev": "dev",
        }
        return alias_map.get(token)

    def handle_dev_window_command(self, args: list[str]):
        if not args:
            self.append_dev_output("usage: window list | window open|close|focus <name>", "red")
            return

        action = args[0].lower()
        if action == "list":
            lines = ["windows", ""]
            for key in [
                "terminal",
                "log",
                "player",
                "target",
                "objective",
                "route",
                "databank",
                "settings",
                "payload",
                "tutorial",
                "dev",
            ]:
                window = self.floating_windows[key]
                visibility = "visible" if window.isVisible() else "hidden"
                active = " active" if window.property("active") else ""
                lines.append(f"{key:<10} {visibility}{active}")
            self.append_dev_output("\n".join(lines), "white")
            return

        if len(args) < 2:
            self.append_dev_output("usage: window open|close|focus <name>", "red")
            return

        key = self.resolve_dev_window_key(args[1])
        if not key or key not in self.floating_windows:
            self.append_dev_output(f"unknown window: {args[1]}", "red")
            return

        window = self.floating_windows[key]
        if action == "open":
            if key == "tutorial":
                self.open_tutorial_window()
            elif key == "dev":
                self.open_dev_console()
            else:
                window.restore_window()
            self.append_dev_output(f"opened {key}.", "green")
            return
        if action == "close":
            window.hide_window()
            self.append_dev_output(f"closed {key}.", "green")
            return
        if action == "focus":
            if not window.isVisible():
                if key == "tutorial":
                    self.open_tutorial_window()
                elif key == "dev":
                    self.open_dev_console()
                else:
                    window.restore_window()
            self.activate_window(key)
            self.append_dev_output(f"focused {key}.", "green")
            return

        self.append_dev_output(f"unknown window action: {action}", "red")

    def handle_dev_layout_command(self, args: list[str]):
        if not args or args[0].lower() != "reset":
            self.append_dev_output("usage: layout reset", "red")
            return
        self.reset_window_layout()
        self.append_dev_output("desktop layout reset.", "green")

    def build_script_synopsis(self, script_id: str, data: dict, allowed_flags: list[str]) -> str:
        synopsis = script_id
        if data.get("supports_target", True):
            if data.get("default_target"):
                synopsis += f" [-target {str(data.get('default_target')).upper()}]"
            else:
                synopsis += " -target <OS|SEC|NET|MEM|STO>"
        if allowed_flags:
            synopsis += " [" + " ".join(allowed_flags) + "]"
        return synopsis

    def build_databank_entry_text(self, entry) -> str:
        kind = entry["kind"]
        item_id = entry["id"]
        data = entry["data"]

        class_role_map = {
            "scan": "collect telemetry and service intel",
            "brute_force": "apply loud direct pressure",
            "exploit": "abuse exposed surfaces",
            "utility": "defend, recover, or control tempo",
        }

        lines = [f"{entry['title']} // {kind}", ""]

        if kind == "script":
            allowed_flags = self.backend.arsenal.get_owned_allowed_flags(item_id, self.backend.player)
            class_name = str(data.get("type", "tool")).replace("_", "-")
            supports_target = data.get("supports_target", True)
            default_target = data.get("default_target")
            lines.extend(
                [
                    "SYNOPSIS",
                    f" {self.build_script_synopsis(item_id, data, allowed_flags)}",
                    "",
                    "PROFILE",
                    f" ram cost       {data.get('ram', 0)}",
                    f" class          {class_name}",
                    f" class role     {class_role_map.get(str(data.get('type', 'tool')), 'special action')}",
                ]
            )
            if not supports_target:
                lines.append(" targeting      fixed-domain only")
            elif default_target:
                lines.append(f" targeting      defaults to {str(default_target).upper()}")
            elif str(data.get("type", "tool")) in {"brute_force", "exploit"}:
                lines.append(" targeting      defaults to OS")
            else:
                lines.append(" targeting      manual or script-defined")
            if data.get("damage", 0):
                lines.append(f" base damage    {data.get('damage', 0)}")
            if data.get("repair", 0):
                lines.append(f" repair         {data.get('repair', 0)}")
            if data.get("default_target"):
                lines.append(f" default target {data.get('default_target')}")
            aliases = ", ".join(data.get("aliases", [])) or "none"
            lines.append(f" aliases        {aliases}")
            lines.append(f" installed flags {', '.join(allowed_flags) or 'none'}")
            effects = self.describe_script_effects(item_id, data)
        elif kind == "flag":
            lines.extend(
                [
                    "SYNOPSIS",
                    f" {item_id} <script>",
                    "",
                    "PROFILE",
                    f" ram cost       +{data.get('ram', 0)}",
                    " class          modifier",
                    " class role     changes how a script behaves",
                ]
            )
            effects = self.describe_flag_effects(item_id, data)
        elif kind == "target":
            lines.extend(
                [
                    "SYNOPSIS",
                    f" target {item_id}",
                    "",
                    "PROFILE",
                    " class          subsystem",
                    " class role     part of a host you can attack or scan",
                ]
            )
            effects = self.describe_target_effects(item_id)
        else:
            amount = self.backend.player.get_consumable_count(item_id) if self.backend.player else 0
            lines.extend(
                [
                    "SYNOPSIS",
                    f" use {item_id}" + (" -target <OS|SEC|NET|MEM|STO>" if data.get("requires_target") else ""),
                    "",
                    "PROFILE",
                    " class          consumable",
                    f" inventory      {amount}",
                    " class role     one-time tactical tool",
                ]
            )
            if data.get("requires_target"):
                lines.append(" target         required")
            effects = self.describe_item_effects(data)

        if kind == "target":
            description = self.backend.get_manual_entry(item_id.lower()) or "No description loaded."
        else:
            description = data.get("description", "No description loaded.")
        lines.extend(["", "DESCRIPTION", f" {description}"])
        if effects:
            lines.extend(["", "EFFECTS"])
            for effect in effects:
                lines.append(f" - {effect}")
        return "\n".join(lines)

    @staticmethod
    def describe_script_effects(script_id: str, data: dict) -> list[str]:
        effects = []
        if data.get("damage"):
            effects.append(f"It deals {data['damage']} base damage before flags, defenses, and reactions.")
        if data.get("repair"):
            effects.append(f"It restores {data['repair']} Core OS integrity.")
        if data.get("disrupt_turns"):
            effects.append(f"It peels back SEC for {data['disrupt_turns']} turn(s).")
        if data.get("guard"):
            effects.append(f"It creates a {data['guard']}-point ACL shell for {data.get('turns', 1)} turn(s).")
        if data.get("trap_damage"):
            effects.append(f"It fires back for {data['trap_damage']} damage when triggered.")
        if data.get("ratio"):
            effects.append(f"It reflects hostile pressure at {int(data['ratio'] * 100)}% strength.")
        if data.get("flat_damage"):
            effects.append(f"It adds {data['flat_damage']} flat feedback damage.")
        if script_id == "ping":
            effects.append("Successful hits leave a short timing mark, making same-lane follow-up payloads land cleaner.")
        if script_id == "nmap":
            effects.append("Targeted fingerprinting primes later exploit payloads on that lane.")
        if script_id == "spray":
            effects.append("Successful auth pressure primes the lane for stronger Hydra follow-up.")
        if script_id == "sqlmap":
            effects.append("Endpoint hits from dirb make later injections hit harder.")
        if script_id == "shred":
            effects.append("Damaged MEM and STO lanes can be kept from recovering for a short window.")
        if script_id == "overflow":
            effects.append("Successful hits on MEM or NET can jam the host's next action.")
        if script_id == "hammer":
            effects.append("Open-core hits can trigger collateral subsystem damage and stall the host's next move.")
        if script_id == "spoof":
            effects.append("It also blurs the host's short-term response model, making recent pattern reads less reliable.")
        if script_id == "harden":
            effects.append("If it matches the lane the host is already winding up on, the ACL shell comes in stronger.")
        if script_id == "rekey":
            effects.append("It also invalidates the host's recent adaptation cache.")
        if script_id == "patch":
            effects.append("It can lightly repair the worst supporting lane and warm a little RAM back up.")
        script_specific = {
            "ping": "Cheap packet pressure for cleanup work. It can also expose hostile timing and mark a lane for cleaner follow-up.",
            "nmap": "Broad port and banner scan. Targeted mode behaves like deeper fingerprinting once SEC is open and sets up exploit work there.",
            "enum": "Pulls exact telemetry and resolves live hostile intent on one subsystem.",
            "whois": "Owner and allocation lookup that also discounts the next recon action.",
            "dirb": "Endpoint discovery for one lane. It also primes later injection work on that lane.",
            "airmon-ng": "Monitor-mode pivot used here to peel back perimeter controls on SEC.",
            "hydra": "Rapid credential brute force. It improves on auth lanes and gets stronger after spray pressure.",
            "sqlmap": "Database and web injection pressure. It gets stronger once dirb already found exposed paths.",
            "spray": "Password spray pressure that can wobble perimeter or broker services and prime later hydra bursts.",
            "shred": "Destructive wipe routine that spikes once a lane is unstable and slows repair afterward.",
            "overflow": "Memory corruption payload for MEM- and NET-heavy runtime services; successful hits can jam the next hostile action.",
            "hammer": "Homebrew crash harness for already-open cores that can force a panic spill.",
            "spoof": "Rolls hostile recon back and muddies the host's short-term traffic model.",
            "honeypot": "Poisons the next hostile scan with decoy telemetry.",
            "canary": "Arm it where you think the next hostile action will land.",
            "sinkhole": "Reflect the next committed hostile action on one lane.",
            "rekey": "Session hygiene under fire: clears RAM locks, strips back recon, and resets hostile cacheing.",
            "patch": "Small repair cycle without spending an item, with a bit of supporting stabilization.",
        }
        if script_id in script_specific:
            effects.append(script_specific[script_id])
        if not effects:
            effects.append("No extra combat riders beyond its main effect.")
        return effects

    @staticmethod
    def describe_flag_effects(flag_id: str, data: dict) -> list[str]:
        effects = []
        if data.get("damage_bonus"):
            effects.append(f"It adds +{data['damage_bonus']} damage.")
        if data.get("noise_bonus"):
            effects.append(f"It adds +{data['noise_bonus']} trace noise.")
        if data.get("exposure_delta"):
            effects.append(f"It changes recon exposure by {data['exposure_delta']}.")
        flag_specific = {
            "--ransom": "Wraps the payload in monetization logic. You only get paid if damage actually lands.",
            "--stealth": "Higher-cost low-observable wrapper.",
            "--ghost": "Cheaper OPSEC wrapper for recon-heavy turns.",
            "--worm": "Residual damage propagates if the first lane collapses.",
            "--burst": "Aggressive timing wrapper: more damage, more noise.",
            "--volatile": "Unsafe overclock: harder hit, louder trace.",
            "--fork": "Multi-thread wrapper that spills part of the hit into a second lane.",
        }
        if flag_id in flag_specific:
            effects.append(flag_specific[flag_id])
        if not effects:
            effects.append("Modifier details loaded from the current arsenal.")
        return effects

    @staticmethod
    def describe_item_effects(data: dict) -> list[str]:
        effects = []
        if data.get("amount"):
            effects.append(f"Value: {data['amount']}.")
        if data.get("turns"):
            effects.append(f"Duration: {data['turns']} turn(s).")
        if data.get("trap_damage"):
            effects.append(f"Trap payload: {data['trap_damage']} damage.")
        if data.get("jammer_turns"):
            effects.append(f"Decoy window: {data['jammer_turns']} turn(s).")
        if data.get("scrub_stages"):
            effects.append(f"Scrubs {data['scrub_stages']} hostile recon stage(s).")
        if not effects:
            effects.append("Single-use tactical utility.")
        return effects

    @staticmethod
    def describe_target_effects(target_id: str) -> list[str]:
        return {
            "OS": [
                "Core execution plane. If it crashes, the fight ends.",
                "Subsystem failures can also propagate secondary pressure into OS.",
            ],
            "SEC": [
                "Perimeter and access-control layer. It catches most direct OS pressure.",
                "Breaking it improves later fingerprinting and direct core damage.",
            ],
            "NET": [
                "Routing and scan plane.",
                "Damaging it degrades recon quality, trace routines, and clean disconnects.",
            ],
            "MEM": [
                "Runtime state and allocator pool.",
                "As MEM gets damaged, RAM recovers more slowly every turn.",
                "Every 4 missing MEM HP also cuts 1 effective max RAM.",
            ],
            "STO": [
                "Storage, archives, and cached value.",
                "Breaking it can spill extra loot without ending the fight.",
            ],
        }.get(target_id, ["Subsystem reference entry."])

    @staticmethod
    def describe_script_effects(script_id: str, data: dict) -> list[str]:
        return script_effect_lines(script_id, data)

    @staticmethod
    def describe_flag_effects(flag_id: str, data: dict) -> list[str]:
        return flag_effect_lines(flag_id, data)

    @staticmethod
    def describe_item_effects(data: dict) -> list[str]:
        return item_effect_lines(data)

    @staticmethod
    def describe_target_effects(target_id: str) -> list[str]:
        return target_effect_lines(target_id)

    def refresh_prompt_bar(self):
        tutorial_gate_locked = self.is_tutorial_boot_active() or self.is_tutorial_warmup_gate_active()
        prompt = ""
        if not self.is_tutorial_warmup_gate_active():
            prompt = self.backend.active_prompt if self.backend.active_prompt else ""
        active = bool(prompt.strip())
        self.feed.input_locked = tutorial_gate_locked
        self.feed.set_prompt_state(prompt, active)
        self.feed_highlighter.set_live_prompt(len(self.feed.history_lines) if active else -1, prompt if active else "")
        if active and not self._prompt_was_active and not tutorial_gate_locked:
            self.input.setFocus()
            self.feed.move_cursor_to_end()
        self._prompt_was_active = active

    def refresh_taskbar(self):
        if self.main_menu_active:
            for button in self.window_buttons.values():
                button.hide()
            return
        for key, button in self.window_buttons.items():
            window = self.floating_windows[key]
            if key == "tutorial":
                button.hide()
                continue
            if window.isVisible():
                self.taskbar_seen_keys.add(key)
            visible = key in self.taskbar_seen_keys
            if self.is_tutorial_boot_active():
                visible = key in self.tutorial_boot_revealed
            button.setVisible(visible)
            button.setChecked(window.isVisible())
            button.setProperty("active", window.isVisible() and bool(window.property("active")))
            repolish(button)

    def is_tutorial_staging_state(self) -> bool:
        return self.backend.objective_is_tutorial and not self.backend.current_enemy

    def build_objective_text(self) -> str:
        if self.backend.objective_is_tutorial:
            return objective_staging_text(active=not self.is_tutorial_staging_state())

        lines = [
            self.backend.objective_title,
            "",
            self.backend.objective_body.strip(),
        ]
        if self.backend.objective_command:
            lines.append("")
            lines.append(f"TRY: {self.backend.objective_command}")
        if self.backend.objective_detail:
            lines.append(f"WHY: {self.backend.objective_detail}")
        return "\n".join(lines)

    def build_player_text(self) -> str:
        if self.is_tutorial_staging_state():
            return player_staging_text()
        player = self.backend.player
        state = self.backend.state
        if not player or not state:
            return "bootstrapping session state..."

        ram_max = player.get_effective_max_ram()
        ram_regen = player.get_ram_regen()
        lines = [
            f"{player.handle} // {player.title}",
            f"ip {player.local_ip}",
            f"ram {player.current_ram}/{ram_max}  regen {ram_regen}/turn (mem)",
            f"signature {player.signature_subsystem}",
            "",
        ]

        for left, right in [("OS", "SEC"), ("NET", "MEM")]:
            left_sub = player.subsystems[left]
            right_sub = player.subsystems[right]
            lines.append(
                f"{left:<3} {left_sub.current_hp:>2}/{left_sub.max_hp:<2}   "
                f"{right:<3} {right_sub.current_hp:>2}/{right_sub.max_hp:<2}"
            )

        sto = player.subsystems["STO"]
        lines.append(f"STO {sto.current_hp:>2}/{sto.max_hp:<2}")
        lines.append("")
        lines.append(player.get_defense_summary())
        lines.append(player.get_support_bot_summary())
        lines.append(f"items {player.get_consumable_summary()}")
        return "\n".join(lines)

    def build_target_text(self) -> str:
        enemy = self.backend.current_enemy
        if not enemy:
            if self.is_tutorial_staging_state():
                return target_staging_text()
            return target_idle_text()

        owner, role, allocation = enemy.owner_profile
        intel_text = enemy.description if enemy.identity_revealed else "identity unresolved. host profile still masked."
        if enemy.weakness_revealed:
            weakness_text = enemy.weakness
        elif enemy.security_breach_turns > 0 or enemy.subsystems["SEC"].is_destroyed:
            weakness_text = "fingerprint pending"
        else:
            weakness_text = "masked by perimeter controls"

        lines = [
            f"HOST        {enemy.get_visible_name()}",
            f"COUNTER     {enemy.get_visible_weapon()}",
            f"OPERATING   {enemy.subsystems['OS'].name}",
            f"LINK        {enemy.get_recon_alert_text()}",
            f"EXPOSURE    {enemy.recon_exposure}",
            f"PORTS       {enemy.get_service_summary() if enemy.topology_revealed else 'unresolved'}",
            f"VULN        {weakness_text}",
        ]
        if enemy.intent_revealed:
            lines.append(f"INTENT      {enemy.current_intent.get('name', 'Idle')}")
        else:
            lines.append("INTENT      unresolved")

        if enemy.identity_revealed:
            lines.append(f"OWNER       {owner}")
            lines.append(f"ROLE        {role}")
            lines.append(f"NETRANGE    {allocation}")
        else:
            lines.append("OWNER       unresolved")
            lines.append("ROLE        unresolved")
            lines.append("NETRANGE    unresolved")

        adaptation = enemy.get_adaptation_summary()
        if adaptation:
            lines.append(f"ADAPT       {adaptation}")

        lines.append("")
        lines.append("INTEL")
        lines.append(f" {intel_text}")
        lines.append("")
        lines.append("SUBSYSTEMS")
        for key in ("OS", "SEC", "NET", "MEM", "STO"):
            lines.append(self.enemy_subsystem_detail_row(enemy, key))
        return "\n".join(lines)

    @staticmethod
    def enemy_subsystem_row(enemy, left: str, right: str | None = None) -> str:
        def chunk(key: str) -> str:
            subsystem = enemy.subsystems[key]
            if enemy.has_telemetry_for(key):
                label = f"{subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
            elif enemy.topology_revealed:
                label = "layout"
            else:
                label = "??"
            return f"{key:<3} {label}"

        row = chunk(left)
        if right:
            row += f"   {chunk(right)}"
        return row

    @staticmethod
    def enemy_subsystem_detail_row(enemy, key: str) -> str:
        subsystem = enemy.subsystems[key]
        if enemy.has_telemetry_for(key):
            status = f"{subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
        elif enemy.topology_revealed:
            status = "layout"
        else:
            status = "??"
        pressure = enemy.classify_pressure(subsystem)
        return f" {key:<3} {subsystem.name:<10} {status:<7} {pressure}"

    def build_route_text(self) -> str:
        if self.is_tutorial_staging_state():
            return route_staging_text()
        return self.build_route_map_text()

    def build_log_text(self) -> str:
        if self.is_tutorial_staging_state():
            return log_staging_text()
        return self.backend.build_shell_session_log_text()

    def build_route_map_text(self) -> str:
        world = self.backend.map_world
        if not world:
            if self.backend.current_enemy:
                enemy = self.backend.current_enemy
                host_name = enemy.get_visible_name() if enemy.identity_revealed else "training link"
                return isolated_route_text(host_name)
            return "> awaiting route mesh..."

        focus_index = self.backend.map_active
        if focus_index is None:
            focus_index = min(world.entry_links) if world.entry_links else 0
        focus_node = world.nodes[focus_index]

        lines = [
            world.subnet_name,
            self.backend.map_status or "mesh idle",
            "",
            "[active node]",
            f" {self.describe_route_node(world, focus_index, focus_node)}",
        ]

        active_intel = self.backend.build_node_intel_summary(focus_node)
        if active_intel:
            lines.append(f"  {active_intel}")

        neighbor_indices = sorted(
            world.links.get(focus_index, set()),
            key=lambda idx: (world.node_depths.get(idx, 99), world.nodes[idx].ip_address),
        )
        if not neighbor_indices:
            lines.extend(["", "linked hops", " none"])
        else:
            lines.extend(["", "linked hops"])
            for position, node_index in enumerate(neighbor_indices):
                node = world.nodes[node_index]
                branch = "`-" if position == len(neighbor_indices) - 1 else "|-"
                lines.append(f" {branch} {self.describe_route_node(world, node_index, node)}")
                intel = self.route_node_secondary_line(world, focus_index, node_index, node)
                if intel:
                    spacer = "   " if position == len(neighbor_indices) - 1 else "|  "
                    lines.append(f" {spacer}{intel}")

                next_hops = sorted(
                    linked for linked in world.links.get(node_index, set()) if linked != focus_index
                )
                if next_hops:
                    preview = ", ".join(self.route_node_short_label(world, linked) for linked in next_hops[:3])
                    spacer = "   " if position == len(neighbor_indices) - 1 else "|  "
                    lines.append(f" {spacer}next: {preview}")

        lines.extend(["", "mail = dead-drop inbox", "bot = bot bay"])
        return "\n".join(lines)

    def describe_route_node(self, world, node_index: int, node) -> str:
        status = self.backend.get_node_status_text(node_index, node, self.backend.map_cleared)
        label = self.route_node_label(world, node_index, node)
        if label == node.ip_address:
            return f"{label} [{status}]"
        return f"{label} @ {node.ip_address} [{status}]"

    def route_node_secondary_line(self, world, focus_index: int, node_index: int, node) -> str | None:
        status = self.backend.get_node_status_text(node_index, node, self.backend.map_cleared)
        if status == "LOCKED":
            unlock_source_indexes = world.get_unlock_sources(node_index)
            if focus_index in unlock_source_indexes:
                return "clear active node to open route"
            unlock_sources = [world.nodes[source_index].ip_address for source_index in unlock_source_indexes]
            if unlock_sources:
                return "route via " + " / ".join(unlock_sources[:2])
        return self.backend.build_node_intel_summary(node)

    def route_node_label(self, world, node_index: int, node) -> str:
        if node.node_type == "shop":
            return "market relay"

        enemy = getattr(node, "cached_enemy", None)
        if enemy and enemy.identity_revealed:
            return enemy.get_visible_name().split("[")[0].strip()

        if node_index in self.backend.map_cleared and enemy and enemy.topology_revealed:
            scanned = self.backend.get_node_scan_label(enemy).strip()
            if scanned and scanned not in {"HOSTILE", "SCANNED"}:
                return scanned.title()

        return node.ip_address

    def route_node_short_label(self, world, node_index: int) -> str:
        node = world.nodes[node_index]
        label = self.route_node_label(world, node_index, node)
        if label == node.ip_address:
            return node.ip_address.split(".")[-1]
        short = label.split("@", 1)[0].strip()
        return short[:14]

    @staticmethod
    def build_architecture_text(enemy) -> str:
        def label(key: str):
            subsystem = enemy.subsystems[key]
            if enemy.has_telemetry_for(key):
                return f"{key} {subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
            if enemy.topology_revealed:
                return f"{key} layout"
            return f"{key} ??"

        sec_label = label("SEC")
        net_label = label("NET")
        os_label = label("OS")
        mem_label = label("MEM")
        sto_label = label("STO")

        lines = [
            "host architecture",
            "",
            "             [ " + sec_label + " ]",
            "                  |",
            "[ " + net_label + " ]--[ " + os_label + " ]--[ " + mem_label + " ]",
            "                  |",
            "             [ " + sto_label + " ]",
            "",
        ]

        if enemy.topology_revealed:
            lines.append("open services:")
            for entry in enemy.get_surface_report_lines():
                lines.append(entry.strip())
        else:
            lines.append("blind tap. no port map resolved.")
        return "\n".join(lines)

    def build_databank_text(self) -> str:
        if self.is_tutorial_staging_state():
            return databank_staging_text()
        arsenal = getattr(self.backend, "arsenal", None)
        if not arsenal:
            return "\n".join(self.backend.databank_lines)

        script_ids, flag_ids, include_items = self.get_visible_databank_entries()
        return "\n".join(self.compose_databank_lines(arsenal, script_ids, flag_ids, include_items))

    def compose_databank_lines(self, arsenal, script_ids, flag_ids, include_items: bool) -> list[str]:
        lines = ["TOOLS", " name         ram  class"]
        for name in script_ids:
            data = arsenal.scripts.get(name)
            if not data:
                continue
            role = self.backend.databank_role_label("script", name, data)
            lines.append(f" {name:<12} {data['ram']:>2}   {role:<10}")

        lines.extend(["", "FLAGS", " flag         ram  class"])
        for flag in flag_ids:
            data = arsenal.flags.get(flag)
            if not data:
                continue
            role = self.backend.databank_role_label("flag", flag, data)
            lines.append(f" {flag:<12} +{data['ram']:<2}  {role:<10}")

        if include_items and self.backend.item_library:
            lines.extend(["", "ITEMS", " item         mode  qty"])
            for item_id in sorted(self.backend.item_library):
                if self.backend.player and self.backend.player.get_consumable_count(item_id) <= 0:
                    continue
                data = self.backend.item_library[item_id]
                role = self.backend.databank_role_label("item", item_id, data)
                amount = self.backend.player.get_consumable_count(item_id) if self.backend.player else 0
                lines.append(f" {item_id:<12} {role:<5} {amount}")

        lines.extend(
            [
                "",
                "TARGETS",
                " target       role",
                " OS           kill",
                " SEC          firewall",
                " NET          network",
                " MEM          memory",
                " STO          storage",
            ]
        )
        return lines

    def get_visible_databank_entries(self):
        arsenal = getattr(self.backend, "arsenal", None)
        if not arsenal:
            return [], [], False

        player = getattr(self.backend, "player", None)
        if player:
            scripts = [script_id for script_id in arsenal.scripts if player.owns_script(script_id)]
            flags = [flag_id for flag_id in arsenal.flags if player.owns_flag(flag_id)]
            include_items = any(player.get_consumable_count(item_id) > 0 for item_id in self.backend.item_library)
            return scripts, flags, include_items

        return list(arsenal.scripts.keys()), list(arsenal.flags.keys()), bool(self.backend.item_library)

    def build_tutorial_overlay(self):
        if self.is_tutorial_boot_active():
            steps = self.get_tutorial_boot_steps()
            step = steps[min(self.tutorial_boot_step, len(steps) - 1)]
            return build_boot_tutorial_overlay(
                get_tutorial_boot_steps()[min(self.tutorial_boot_step, len(get_tutorial_boot_steps()) - 1)]
            )

        if self.is_tutorial_warmup_gate_active():
            return build_warmup_gate_overlay(self.tutorial_warmup_requested)

        title = self.backend.objective_title.strip().upper()
        enemy = self.backend.current_enemy

        if enemy and enemy.id == "training_drone":
            if enemy.subsystems["SEC"].current_hp == enemy.subsystems["SEC"].max_hp:
                return build_drone_tutorial_overlay("ping_sec")
            if enemy.subsystems["SEC"].current_hp > 0:
                return build_drone_tutorial_overlay("break_sec")
            return build_drone_tutorial_overlay("finish_os")

        if title == "SANDBOX ALERT":
            return sandbox_alert_overlay()

        if enemy and enemy.id == "aegis_black_ice":
            return black_ice_overlay()

        return "", set()

    def set_guided_windows(self, keys: set[str]):
        coach_window = self.floating_windows.get("tutorial")
        coach_guided = self.backend.objective_is_tutorial and (
            self.is_tutorial_boot_active()
            or self.is_tutorial_warmup_gate_active()
            or bool(self.backend.current_enemy and self.backend.current_enemy.id == "training_drone")
        )
        for name, window in self.floating_windows.items():
            if name == "tutorial":
                window.set_guided(coach_guided)
            elif name == "payload":
                window.set_guided(False)
            else:
                window.set_guided(name in keys)

    def sync_tutorial_overlay(self, *, force_show: bool = False):
        window = self.floating_windows["tutorial"]
        if not self.backend.objective_is_tutorial:
            self.set_guided_windows(set())
            self._last_tutorial_signature = ""
            self.tutorial_boot_started = False
            self.tutorial_boot_complete = False
            self.tutorial_boot_step = 0
            self.tutorial_boot_revealed = set()
            self.tutorial_warmup_requested = False
            self.tutorial_warmup_gate_pending = False
            self.feed.input_locked = False
            if window.isVisible():
                window.hide()
            return

        if not self.tutorial_boot_started:
            self.start_tutorial_boot_sequence()

        if self.tutorial_warmup_gate_pending and self.backend.current_enemy:
            self.tutorial_warmup_gate_pending = False

        text, focused = self.build_tutorial_overlay()
        if not text:
            self.set_guided_windows(set())
            if window.isVisible():
                window.hide()
            return

        self.tutorial_detail.set_text(text)
        self.set_guided_windows(set(focused))
        focus_key = next(iter(focused), None)

        signature = f"{self.backend.objective_title}|{text}"
        if signature != self._last_tutorial_signature or force_show:
            self.position_tutorial_window(focus_key)

            if focus_key and focus_key in self.floating_windows:
                self.activate_window(focus_key)
                if focus_key == "terminal" and self.feed.prompt_active and not self.is_tutorial_boot_active():
                    self.feed.current_input = ""
                    self.feed._sync_view()
                    self.input.setFocus()
                    self.feed.move_cursor_to_end()

            window.show()
            window.raise_()
            self._last_tutorial_signature = signature
        elif window.isVisible():
            window.raise_()


def launch():
    app = QApplication.instance() or QApplication(sys.argv)
    window = TerminalRoguePySideWindow()
    window.showMaximized()
    app.exec()


def main():
    launch()


if __name__ == "__main__":
    main()
