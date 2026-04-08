from __future__ import annotations

import builtins
import math
import os
import re
import shlex
import sys
import threading
from time import monotonic
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
    QPainterPath,
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
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QToolTip,
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
    build_window_boot_snapshot,
    build_window_boot_text,
    databank_staging_text,
    dev_console_banner_lines,
    get_boot_menu_loading_copy,
    get_tutorial_boot_steps,
    get_window_boot_sequence,
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


class RouteMapCanvas(QWidget):
    def __init__(self, label_provider, status_provider, intel_provider):
        super().__init__()
        self.label_provider = label_provider
        self.status_provider = status_provider
        self.intel_provider = intel_provider
        self.world = None
        self.cleared_nodes: set[int] = set()
        self.active_index: int | None = None
        self.status_text = ""
        self.staging = False
        self.staging_text = ""
        self.node_regions: dict[int, QRect] = {}
        self.pan_offset = QPoint(0, 0)
        self._dragging = False
        self._drag_origin = QPoint()
        self._drag_start_offset = QPoint()
        self._layout_cache_key = None
        self._layout_cache = None
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("routeCanvas")
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_network_state(
        self,
        world,
        cleared_nodes,
        active_index,
        status_text,
        *,
        staging: bool = False,
        staging_text: str = "",
    ):
        world_changed = world is not self.world
        active_changed = active_index != self.active_index
        self.world = world
        self.cleared_nodes = set(cleared_nodes or set())
        self.active_index = active_index
        self.status_text = status_text or ""
        self.staging = staging
        self.staging_text = staging_text
        self.node_regions = {}
        self._layout_cache_key = None
        self._layout_cache = None
        if world_changed or active_changed:
            self.pan_offset = QPoint(0, 0)
        self.update()

    def _combined_links(self, node_index: int) -> list[int]:
        if not self.world:
            return []
        neighbors = set(self.world.get_inbound_hops(node_index))
        neighbors.update(self.world.get_outbound_hops(node_index))
        return sorted(neighbors)

    def _focus_index(self) -> int | None:
        if not self.world or not getattr(self.world, "nodes", None):
            return None
        if self.active_index is not None and 0 <= self.active_index < len(self.world.nodes):
            return self.active_index
        if self.world.entry_links:
            return min(self.world.entry_links)
        return 0

    def _build_tree(self, focus_index: int):
        distances = {focus_index: 0}
        parent: dict[int, int | None] = {focus_index: None}
        queue = [focus_index]

        while queue:
            current = queue.pop(0)
            for neighbor in self._combined_links(current):
                if neighbor in distances:
                    continue
                distances[neighbor] = distances[current] + 1
                parent[neighbor] = current
                queue.append(neighbor)

        children: dict[int, list[int]] = {index: [] for index in distances}
        for node_index, parent_index in parent.items():
            if parent_index is None:
                continue
            children.setdefault(parent_index, []).append(node_index)

        for node_index in children:
            children[node_index].sort(
                key=lambda idx: (
                    self.world.node_depths.get(idx, 99),
                    self.label_provider(self.world, idx, self.world.nodes[idx]).lower(),
                )
            )
        return distances, parent, children

    def _build_component(self, root_index: int, allowed_nodes: set[int] | None = None):
        distances = {root_index: 0}
        parent: dict[int, int | None] = {root_index: None}
        queue = [root_index]

        while queue:
            current = queue.pop(0)
            for neighbor in self._combined_links(current):
                if allowed_nodes is not None and neighbor not in allowed_nodes:
                    continue
                if neighbor in distances:
                    continue
                distances[neighbor] = distances[current] + 1
                parent[neighbor] = current
                queue.append(neighbor)

        children: dict[int, list[int]] = {index: [] for index in distances}
        for node_index, parent_index in parent.items():
            if parent_index is None:
                continue
            children.setdefault(parent_index, []).append(node_index)

        for node_index in children:
            children[node_index].sort(
                key=lambda idx: (
                    self.world.node_depths.get(idx, 99),
                    self.label_provider(self.world, idx, self.world.nodes[idx]).lower(),
                )
            )
        return distances, parent, children

    def _edge_pairs(self, node_indexes: set[int]) -> list[tuple[int, int]]:
        if not self.world:
            return []
        edges: set[tuple[int, int]] = set()
        for source_index, linked in getattr(self.world, "forward_links", {}).items():
            if source_index not in node_indexes:
                continue
            for target_index in linked:
                if target_index in node_indexes:
                    edges.add((source_index, target_index))
        return sorted(edges)

    def _graph_signature(self) -> tuple:
        if not self.world:
            return ()
        forward_links = getattr(self.world, "forward_links", {})
        edge_signature = tuple(
            sorted((source, tuple(sorted(targets))) for source, targets in forward_links.items())
        )
        depth_signature = tuple(sorted(getattr(self.world, "node_depths", {}).items()))
        return (
            id(self.world),
            len(getattr(self.world, "nodes", [])),
            edge_signature,
            depth_signature,
        )

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= math.tau
        while angle < -math.pi:
            angle += math.tau
        return angle

    def _layout_radial_component(
        self,
        *,
        center_x: float,
        center_y: float,
        root_index: int,
        distances: dict[int, int],
        children: dict[int, list[int]],
        ring_step: float,
        anchor_angle: float,
    ) -> tuple[dict[int, list[float]], dict[int, float]]:
        positions_float: dict[int, list[float]] = {root_index: [center_x, center_y]}
        anchor_angles: dict[int, float] = {root_index: anchor_angle}

        def stable_jitter(node_index: int) -> float:
            return ((((node_index * 37) % 17) / 16.0) - 0.5) * 0.32

        def orbit_scale(node_index: int) -> float:
            return 1.0 + ((((node_index * 19) % 9) - 4) * 0.03)

        def assign_children(node_index: int, parent_angle: float, inherited_span: float):
            child_nodes = children.get(node_index, [])
            if not child_nodes:
                return

            child_count = len(child_nodes)
            if node_index == root_index:
                span = min(math.tau * 0.9, 1.9 + child_count * 0.42)
            else:
                span = min(math.pi * 1.3, max(0.92, inherited_span * 0.8 + child_count * 0.12))

            for order, child_index in enumerate(child_nodes):
                distance = max(1, distances.get(child_index, 1))
                if child_count == 1:
                    swing = 0.7 + 0.12 * ((distance + child_index) % 4)
                    direction = -1.0 if (child_index + distance) % 2 else 1.0
                    angle = self._normalize_angle(parent_angle + direction * swing + stable_jitter(child_index))
                else:
                    relative = ((order + 0.5) / child_count) - 0.5
                    angle = self._normalize_angle(parent_angle + relative * span + stable_jitter(child_index))

                radius = ring_step * distance * orbit_scale(child_index)
                positions_float[child_index] = [
                    center_x + math.cos(angle) * radius,
                    center_y + math.sin(angle) * radius,
                ]
                anchor_angles[child_index] = angle
                assign_children(child_index, angle, span)

        assign_children(root_index, anchor_angle, math.pi * 1.2)
        return positions_float, anchor_angles

    def _layout_positions(self, rect: QRect):
        focus_index = self._focus_index()
        if focus_index is None:
            return None, {}, {}

        distances, _parent, children = self._build_tree(focus_index)
        graph_signature = self._graph_signature()
        cache_key = (rect.width(), rect.height(), focus_index, graph_signature)
        if self._layout_cache_key == cache_key and self._layout_cache is not None:
            return self._layout_cache

        max_distance = max(distances.values(), default=0)
        center_x = float(rect.center().x())
        center_y = float(rect.center().y()) + 8.0
        margin_x = 66.0
        margin_y = 34.0
        min_x = rect.left() + margin_x + 8.0
        max_x = rect.right() - margin_x - 8.0
        min_y = rect.top() + margin_y + 8.0
        max_y = rect.bottom() - margin_y - 8.0
        focus_fit_radius = max(
            96.0,
            min(
                center_x - min_x,
                max_x - center_x,
                center_y - min_y,
                max_y - center_y,
            ),
        )
        preferred_radius = max(156.0, min(rect.width(), rect.height()) * 0.5)
        usable_radius = min(preferred_radius, focus_fit_radius)
        ring_step = usable_radius / max(1, max_distance)
        positions_float, anchor_angles = self._layout_radial_component(
            center_x=center_x,
            center_y=center_y,
            root_index=focus_index,
            distances=distances,
            children=children,
            ring_step=ring_step,
            anchor_angle=-math.pi / 2,
        )

        all_node_indexes = set(range(len(self.world.nodes)))
        connected_indexes = set(distances)
        remaining_indexes = all_node_indexes - connected_indexes

        if remaining_indexes:
            component_centers = [
                5 * math.pi / 6,
                math.pi,
                -5 * math.pi / 6,
                math.pi / 2,
                -math.pi / 2,
                math.pi / 6,
                -math.pi / 6,
            ]
            components: list[set[int]] = []
            unseen = set(remaining_indexes)
            while unseen:
                component_root = min(unseen, key=lambda idx: (self.world.node_depths.get(idx, 99), idx))
                component_distances, _component_parent, _component_children = self._build_component(component_root, unseen)
                component_nodes = set(component_distances)
                components.append(component_nodes)
                unseen -= component_nodes

            for component_order, component_nodes in enumerate(components):
                component_root = min(component_nodes, key=lambda idx: (self.world.node_depths.get(idx, 99), idx))
                component_distances, _component_parent, component_children = self._build_component(component_root, component_nodes)
                anchor = component_centers[component_order % len(component_centers)]
                component_center_radius = usable_radius * (0.86 if len(components) == 1 else 0.94)
                component_center_x = center_x + math.cos(anchor) * component_center_radius
                component_center_y = center_y + math.sin(anchor) * component_center_radius
                component_max_distance = max(component_distances.values(), default=1)
                component_fit_radius = max(
                    72.0,
                    min(
                        component_center_x - min_x,
                        max_x - component_center_x,
                        component_center_y - min_y,
                        max_y - component_center_y,
                    ),
                )
                component_ring_step = min(max(72.0, ring_step * 0.72), component_fit_radius / max(1, component_max_distance))
                component_positions, component_angles = self._layout_radial_component(
                    center_x=component_center_x,
                    center_y=component_center_y,
                    root_index=component_root,
                    distances=component_distances,
                    children=component_children,
                    ring_step=component_ring_step,
                    anchor_angle=anchor,
                )
                positions_float.update(component_positions)
                anchor_angles.update(component_angles)

        approx_node_w = max(92.0, min(134.0, rect.width() / 3.0))
        approx_node_h = 42.0
        node_indexes = all_node_indexes
        distance_guides = {
            node_index: distances.get(node_index, max(1, self.world.node_depths.get(node_index, 1)))
            for node_index in node_indexes
        }
        edges = self._edge_pairs(node_indexes)
        desired_separation = max(118.0, min(186.0, rect.width() * 0.22))

        for _ in range(90):
            forces = {node_index: [0.0, 0.0] for node_index in node_indexes}

            node_list = list(node_indexes)
            for index, node_a in enumerate(node_list):
                ax, ay = positions_float[node_a]
                for node_b in node_list[index + 1 :]:
                    bx, by = positions_float[node_b]
                    dx = ax - bx
                    dy = ay - by
                    distance = math.hypot(dx, dy)
                    if distance < 0.001:
                        distance = 0.001
                        dx = 0.001
                    repel = min(2400.0, (desired_separation * desired_separation) / distance)
                    if distance < desired_separation:
                        repel *= 1.8
                    nx = dx / distance
                    ny = dy / distance
                    forces[node_a][0] += nx * repel
                    forces[node_a][1] += ny * repel
                    forces[node_b][0] -= nx * repel
                    forces[node_b][1] -= ny * repel

            for source_index, target_index in edges:
                sx, sy = positions_float[source_index]
                tx, ty = positions_float[target_index]
                dx = tx - sx
                dy = ty - sy
                distance = math.hypot(dx, dy)
                if distance < 0.001:
                    continue
                depth_gap = max(1, abs(distances.get(target_index, 1) - distances.get(source_index, 1)))
                preferred_length = ring_step * max(0.92, depth_gap)
                stretch = (distance - preferred_length) * 0.12
                nx = dx / distance
                ny = dy / distance
                forces[source_index][0] += nx * stretch
                forces[source_index][1] += ny * stretch
                forces[target_index][0] -= nx * stretch
                forces[target_index][1] -= ny * stretch

            for node_index in node_indexes:
                if node_index == focus_index:
                    positions_float[node_index] = [center_x, center_y]
                    continue

                px, py = positions_float[node_index]
                rx = px - center_x
                ry = py - center_y
                radius = math.hypot(rx, ry)
                if radius < 0.001:
                    rx = 0.001
                    radius = 0.001
                desired_radius = ring_step * distance_guides[node_index]
                radial_pull = (desired_radius - radius) * 0.14
                forces[node_index][0] += (rx / radius) * radial_pull
                forces[node_index][1] += (ry / radius) * radial_pull

                current_angle = math.atan2(ry, rx)
                target_angle = anchor_angles.get(node_index, current_angle)
                angle_delta = self._normalize_angle(target_angle - current_angle)
                tangent_x = -math.sin(current_angle)
                tangent_y = math.cos(current_angle)
                tangential_pull = angle_delta * max(desired_radius, 32.0) * 0.28
                forces[node_index][0] += tangent_x * tangential_pull
                forces[node_index][1] += tangent_y * tangential_pull

            for node_index in node_indexes:
                if node_index == focus_index:
                    continue
                fx, fy = forces[node_index]
                positions_float[node_index][0] += fx * 0.0024
                positions_float[node_index][1] += fy * 0.0024

        min_x = rect.left() + max(margin_x, approx_node_w / 2.0) + 8.0
        max_x = rect.right() - max(margin_x, approx_node_w / 2.0) - 8.0
        min_y = rect.top() + max(margin_y, approx_node_h / 2.0) + 8.0
        max_y = rect.bottom() - max(margin_y, approx_node_h / 2.0) - 8.0

        for _ in range(80):
            moved = False
            for node_a in sorted(node_indexes):
                if node_a == focus_index:
                    continue
                ax, ay = positions_float[node_a]
                for node_b in sorted(node_indexes):
                    if node_b <= node_a:
                        continue
                    bx, by = positions_float[node_b]
                    overlap_x = (approx_node_w + 14.0) - abs(ax - bx)
                    overlap_y = (approx_node_h + 10.0) - abs(ay - by)
                    if overlap_x <= 0 or overlap_y <= 0:
                        continue

                    moved = True
                    push_x = overlap_x / 2.0 + 1.0
                    push_y = overlap_y / 2.0 + 1.0

                    if overlap_x < overlap_y:
                        if ax <= bx:
                            delta_ax = -push_x
                            delta_bx = push_x
                        else:
                            delta_ax = push_x
                            delta_bx = -push_x
                        delta_ay = 0.0
                        delta_by = 0.0
                    else:
                        if ay <= by:
                            delta_ay = -push_y
                            delta_by = push_y
                        else:
                            delta_ay = push_y
                            delta_by = -push_y
                        delta_ax = 0.0
                        delta_bx = 0.0

                    if node_a != focus_index:
                        positions_float[node_a][0] = min(max_x, max(min_x, positions_float[node_a][0] + delta_ax))
                        positions_float[node_a][1] = min(max_y, max(min_y, positions_float[node_a][1] + delta_ay))
                    if node_b != focus_index:
                        positions_float[node_b][0] = min(max_x, max(min_x, positions_float[node_b][0] + delta_bx))
                        positions_float[node_b][1] = min(max_y, max(min_y, positions_float[node_b][1] + delta_by))
            if not moved:
                break

        for node_index in node_indexes:
            if node_index == focus_index:
                positions_float[node_index] = [center_x, center_y]
                continue
            positions_float[node_index][0] = min(max_x, max(min_x, positions_float[node_index][0]))
            positions_float[node_index][1] = min(max_y, max(min_y, positions_float[node_index][1]))

        positions: dict[int, QPoint] = {}
        for node_index, (x_pos, y_pos) in positions_float.items():
            x_pos = max(rect.left() + margin_x, min(int(round(x_pos)), rect.right() - margin_x))
            y_pos = max(rect.top() + margin_y, min(int(round(y_pos)), rect.bottom() - margin_y))
            positions[node_index] = QPoint(x_pos, y_pos)

        min_center_x = int(rect.left() + max(margin_x, approx_node_w / 2.0) + 8.0)
        max_center_x = int(rect.right() - max(margin_x, approx_node_w / 2.0) - 8.0)
        min_center_y = int(rect.top() + max(margin_y, approx_node_h / 2.0) + 8.0)
        max_center_y = int(rect.bottom() - max(margin_y, approx_node_h / 2.0) - 8.0)
        required_gap_x = int(approx_node_w) + 10
        required_gap_y = int(approx_node_h) + 8

        for _ in range(80):
            moved = False
            for node_a in sorted(positions):
                for node_b in sorted(positions):
                    if node_b <= node_a:
                        continue
                    point_a = positions[node_a]
                    point_b = positions[node_b]
                    delta_x = point_b.x() - point_a.x()
                    delta_y = point_b.y() - point_a.y()
                    overlap_x = required_gap_x - abs(delta_x)
                    overlap_y = required_gap_y - abs(delta_y)
                    if overlap_x <= 0 or overlap_y <= 0:
                        continue

                    moved = True
                    move_axis = "x" if overlap_x <= overlap_y else "y"
                    if move_axis == "x":
                        push = overlap_x // 2 + 1
                        if delta_x >= 0:
                            left_push = -push
                            right_push = push
                        else:
                            left_push = push
                            right_push = -push
                        if node_a != focus_index:
                            point_a.setX(max(min_center_x, min(max_center_x, point_a.x() + left_push)))
                        if node_b != focus_index:
                            point_b.setX(max(min_center_x, min(max_center_x, point_b.x() + right_push)))
                    else:
                        push = overlap_y // 2 + 1
                        if delta_y >= 0:
                            up_push = -push
                            down_push = push
                        else:
                            up_push = push
                            down_push = -push
                        if node_a != focus_index:
                            point_a.setY(max(min_center_y, min(max_center_y, point_a.y() + up_push)))
                        if node_b != focus_index:
                            point_b.setY(max(min_center_y, min(max_center_y, point_b.y() + down_push)))

                        if point_a.y() == point_b.y():
                            side_push = overlap_x // 2 + 1
                            if node_a != focus_index:
                                point_a.setX(max(min_center_x, min(max_center_x, point_a.x() - side_push)))
                            if node_b != focus_index:
                                point_b.setX(max(min_center_x, min(max_center_x, point_b.x() + side_push)))
            if not moved:
                break

        result = (focus_index, positions, distances)
        self._layout_cache_key = cache_key
        self._layout_cache = result
        return result

    def _node_style(self, node_index: int, node):
        status = self.status_provider(node_index, node, self.cleared_nodes)
        if node_index == self._focus_index():
            return QColor(PALETTE["cyan"]), QColor(PALETTE["accent_soft"]), QColor(PALETTE["white"]), status
        if status == "CONTESTED":
            return QColor(PALETTE["yellow"]), QColor(60, 42, 18, 220), QColor(PALETTE["white"]), status
        if status == "FORENSIC":
            return QColor(PALETTE["magenta"]), QColor(45, 24, 52, 220), QColor(PALETTE["white"]), status
        if status == "INFECTED":
            return QColor(PALETTE["red"]), QColor(40, 18, 34, 220), QColor(PALETTE["white"]), status
        if status == "LOCKDOWN":
            return QColor(PALETTE["yellow"]), QColor(52, 44, 18, 220), QColor(PALETTE["white"]), status
        if status == "ROOTED":
            return QColor(PALETTE["green"]), QColor(18, 40, 28, 220), QColor(PALETTE["white"]), status
        if status == "BRICKED":
            return QColor(PALETTE["red"]), QColor(44, 20, 24, 220), QColor(PALETTE["white"]), status
        if node_index in self.cleared_nodes:
            return QColor(PALETTE["green"]), QColor(18, 40, 28, 220), QColor(PALETTE["white"]), status
        if status == "LOCKED":
            return QColor(PALETTE["muted"]), QColor(24, 28, 38, 215), QColor(PALETTE["muted"]), status
        if node.node_type == "shop":
            return QColor(PALETTE["yellow"]), QColor(54, 39, 17, 210), QColor(PALETTE["white"]), status
        if node.node_type == "gatekeeper":
            return QColor(PALETTE["red"]), QColor(50, 19, 24, 220), QColor(PALETTE["white"]), status
        return QColor(PALETTE["accent"]), QColor(20, 28, 42, 220), QColor(PALETTE["text"]), status

    def _tooltip_for_node(self, node_index: int) -> str:
        if not self.world:
            return ""
        node = self.world.nodes[node_index]
        status = self.status_provider(node_index, node, self.cleared_nodes)
        label = self.label_provider(self.world, node_index, node)
        intel = self.intel_provider(node)
        lines = [
            f"{label}",
            f"ip: {node.ip_address}",
            f"status: {status}",
            f"depth: {self.world.node_depths.get(node_index, 1)}",
        ]
        if intel:
            lines.append(intel)
        return "\n".join(lines)

    @staticmethod
    def _edge_anchor(center: QPoint, other: QPoint, rect: QRect) -> QPoint:
        dx = other.x() - center.x()
        dy = other.y() - center.y()
        if abs(dx) >= abs(dy):
            return QPoint(rect.right() if dx >= 0 else rect.left(), center.y())
        return QPoint(center.x(), rect.bottom() if dy >= 0 else rect.top())

    @staticmethod
    def _compress_path_points(points: list[QPoint]) -> list[QPoint]:
        if not points:
            return []
        compressed = [points[0]]
        for point in points[1:]:
            if point == compressed[-1]:
                continue
            compressed.append(point)

        simplified = [compressed[0]]
        for point in compressed[1:]:
            if len(simplified) < 2:
                simplified.append(point)
                continue
            prev = simplified[-2]
            current = simplified[-1]
            if (prev.x() == current.x() == point.x()) or (prev.y() == current.y() == point.y()):
                simplified[-1] = point
            else:
                simplified.append(point)
        return simplified

    @staticmethod
    def _segment_hits_rect(start: QPoint, end: QPoint, rect: QRect, padding: int = 10) -> bool:
        padded = rect.adjusted(-padding, -padding, padding, padding)
        if start.x() == end.x():
            x_pos = start.x()
            top = min(start.y(), end.y())
            bottom = max(start.y(), end.y())
            return (
                padded.left() <= x_pos <= padded.right()
                and max(top, padded.top()) <= min(bottom, padded.bottom())
            )
        if start.y() == end.y():
            y_pos = start.y()
            left = min(start.x(), end.x())
            right = max(start.x(), end.x())
            return (
                padded.top() <= y_pos <= padded.bottom()
                and max(left, padded.left()) <= min(right, padded.right())
            )
        return padded.contains(start) or padded.contains(end)

    def _path_block_count(self, points: list[QPoint], blocker_rects: list[QRect]) -> int:
        count = 0
        for start, end in zip(points, points[1:]):
            for rect in blocker_rects:
                if self._segment_hits_rect(start, end, rect):
                    count += 1
        return count

    @staticmethod
    def _path_length(points: list[QPoint]) -> int:
        return sum(abs(end.x() - start.x()) + abs(end.y() - start.y()) for start, end in zip(points, points[1:]))

    def _sample_quadratic_curve(self, start: QPoint, control: QPoint, end: QPoint, *, steps: int = 18) -> list[QPoint]:
        samples: list[QPoint] = []
        for step in range(steps + 1):
            t = step / steps
            inv = 1.0 - t
            x_pos = inv * inv * start.x() + 2.0 * inv * t * control.x() + t * t * end.x()
            y_pos = inv * inv * start.y() + 2.0 * inv * t * control.y() + t * t * end.y()
            samples.append(QPoint(int(round(x_pos)), int(round(y_pos))))
        return self._compress_path_points(samples)

    def _build_link_curve(
        self,
        start: QPoint,
        end: QPoint,
        blocker_rects: list[QRect],
        map_rect: QRect,
    ) -> tuple[QPoint, list[QPoint]]:
        nearby_rects = [
            rect
            for rect in blocker_rects
            if rect.intersects(
                QRect(
                    min(start.x(), end.x()) - 48,
                    min(start.y(), end.y()) - 48,
                    abs(end.x() - start.x()) + 96,
                    abs(end.y() - start.y()) + 96,
                )
            )
        ]

        mid_x = (start.x() + end.x()) / 2.0
        mid_y = (start.y() + end.y()) / 2.0
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = max(1.0, math.hypot(dx, dy))
        perp_x = -dy / length
        perp_y = dx / length
        amplitude = min(108.0, max(36.0, length * 0.32))

        candidate_controls = [
            QPoint(int(round(mid_x)), int(round(mid_y))),
            QPoint(int(round(mid_x + perp_x * amplitude)), int(round(mid_y + perp_y * amplitude))),
            QPoint(int(round(mid_x - perp_x * amplitude)), int(round(mid_y - perp_y * amplitude))),
            QPoint(int(round(mid_x + perp_x * amplitude * 1.5)), int(round(mid_y + perp_y * amplitude * 1.5))),
            QPoint(int(round(mid_x - perp_x * amplitude * 1.5)), int(round(mid_y - perp_y * amplitude * 1.5))),
        ]

        best_control = candidate_controls[0]
        best_samples = self._sample_quadratic_curve(start, best_control, end)
        best_score = None
        for control in candidate_controls:
            control = QPoint(
                max(map_rect.left() + 10, min(map_rect.right() - 10, control.x())),
                max(map_rect.top() + 10, min(map_rect.bottom() - 10, control.y())),
            )
            path = self._sample_quadratic_curve(start, control, end)
            score = (
                self._path_block_count(path, nearby_rects),
                self._path_length(path),
                abs(control.x() - int(round(mid_x))) + abs(control.y() - int(round(mid_y))),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_control = control
                best_samples = path
        return best_control, best_samples

    def resizeEvent(self, event):
        self._layout_cache_key = None
        self._layout_cache = None
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_origin = event.position().toPoint()
            self._drag_start_offset = QPoint(self.pan_offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            QToolTip.hideText()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.position().toPoint() - self._drag_origin
            self.pan_offset = self._drag_start_offset + delta
            self.update()
            event.accept()
            return
        for node_index, rect in self.node_regions.items():
            if rect.contains(event.pos()):
                QToolTip.showText(event.globalPosition().toPoint(), self._tooltip_for_node(node_index), self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pan_offset = QPoint(0, 0)
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(PALETTE["terminal"]))

        header_rect = self.rect().adjusted(8, 6, -8, -8)
        painter.setPen(QColor(PALETTE["muted"]))
        painter.drawText(header_rect.adjusted(0, 0, 0, -header_rect.height() + 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.status_text[:72])

        map_rect = self.rect().adjusted(8, 30, -8, -8)
        self.node_regions = {}

        if self.staging:
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(map_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.staging_text or route_staging_text())
            return

        if not self.world or not getattr(self.world, "nodes", None):
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(map_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "> awaiting route mesh...")
            return

        focus_index, positions, distances = self._layout_positions(map_rect)
        if focus_index is None:
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(map_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "route graph unavailable")
            return

        node_width = max(92, min(134, map_rect.width() // 3))
        node_height = 42
        panned_positions = {
            node_index: QPoint(point.x() + self.pan_offset.x(), point.y() + self.pan_offset.y())
            for node_index, point in positions.items()
        }
        node_rects = {
            node_index: QRect(
                center.x() - node_width // 2,
                center.y() - node_height // 2,
                node_width,
                node_height,
            )
            for node_index, center in panned_positions.items()
        }

        for source_index, linked in getattr(self.world, "forward_links", {}).items():
            if source_index not in panned_positions:
                continue
            for target_index in linked:
                if target_index not in panned_positions:
                    continue
                start_center = panned_positions[source_index]
                end_center = panned_positions[target_index]
                start_rect = node_rects[source_index]
                end_rect = node_rects[target_index]
                start = self._edge_anchor(start_center, end_center, start_rect)
                end = self._edge_anchor(end_center, start_center, end_rect)
                blocker_rects = [
                    rect
                    for node_index, rect in node_rects.items()
                    if node_index not in {source_index, target_index}
                ]
                control_point, sampled_points = self._build_link_curve(start, end, blocker_rects, map_rect)
                target_node = self.world.nodes[target_index]
                target_status = self.status_provider(target_index, target_node, self.cleared_nodes)
                line_color = QColor(PALETTE["green"] if source_index in self.cleared_nodes else PALETTE["panel_border"])
                line_pen = QPen(line_color, 1.5)
                if target_status == "LOCKED":
                    line_pen.setColor(QColor(PALETTE["muted"]))
                    line_pen.setStyle(Qt.PenStyle.DotLine)
                elif target_status in {"BORDER", "MARKET"}:
                    line_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(line_pen)
                path = QPainterPath(start)
                path.quadTo(control_point, end)
                painter.drawPath(path)

                arrow_base = sampled_points[-2] if len(sampled_points) >= 2 else start
                arrow_tip = sampled_points[-1] if sampled_points else end
                angle = math.atan2(arrow_tip.y() - arrow_base.y(), arrow_tip.x() - arrow_base.x())
                arrow_len = 8
                arrow_angle = math.pi / 7
                draw_tip = QPoint(
                    int(arrow_tip.x() - math.cos(angle) * 2),
                    int(arrow_tip.y() - math.sin(angle) * 2),
                )
                left = QPoint(
                    int(draw_tip.x() - math.cos(angle - arrow_angle) * arrow_len),
                    int(draw_tip.y() - math.sin(angle - arrow_angle) * arrow_len),
                )
                right = QPoint(
                    int(draw_tip.x() - math.cos(angle + arrow_angle) * arrow_len),
                    int(draw_tip.y() - math.sin(angle + arrow_angle) * arrow_len),
                )
                painter.drawLine(draw_tip, left)
                painter.drawLine(draw_tip, right)

        font_metrics = painter.fontMetrics()
        small_font = QFont(self.font())
        small_font.setPointSize(max(7, self.font().pointSize() - 1))

        for node_index, node in enumerate(self.world.nodes):
            if node_index not in panned_positions:
                continue
            rect = node_rects[node_index]
            border, fill, text_color, status = self._node_style(node_index, node)
            painter.setPen(QPen(border, 2 if node_index == focus_index else 1.4))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 9, 9)

            label = self.label_provider(self.world, node_index, node)
            label = font_metrics.elidedText(label, Qt.TextElideMode.ElideRight, rect.width() - 12)
            painter.setPen(text_color)
            painter.drawText(rect.adjusted(6, 5, -6, -20), Qt.AlignmentFlag.AlignCenter, label)

            painter.setFont(small_font)
            painter.setPen(QColor(PALETTE["muted"] if status == "LOCKED" else PALETTE["text"]))
            depth_text = f"{status}  d{distances.get(node_index, self.world.node_depths.get(node_index, 1))}"
            painter.drawText(rect.adjusted(6, 21, -6, -4), Qt.AlignmentFlag.AlignCenter, depth_text)
            painter.setFont(self.font())

            self.node_regions[node_index] = rect


class RouteMapPane(QFrame):
    def __init__(self, label_provider, status_provider, intel_provider):
        super().__init__()
        self.setObjectName("paneSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = RouteMapCanvas(label_provider, status_provider, intel_provider)
        layout.addWidget(self.canvas, 1)

    def set_network_state(
        self,
        world,
        cleared_nodes,
        active_index,
        status_text,
        *,
        staging: bool = False,
        staging_text: str = "",
    ):
        self.canvas.set_network_state(
            world,
            cleared_nodes,
            active_index,
            status_text,
            staging=staging,
            staging_text=staging_text,
        )


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
    save_slots_requested = Signal()
    exit_to_menu_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("settingsPane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title = QLabel("Display & Session")
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

        self.save_button = QPushButton("save slots")
        self.save_button.setObjectName("settingsReset")
        self.save_button.clicked.connect(self.save_slots_requested.emit)
        layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.exit_button = QPushButton("exit to main menu")
        self.exit_button.setObjectName("settingsReset")
        self.exit_button.clicked.connect(self.exit_to_menu_requested.emit)
        layout.addWidget(self.exit_button, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

    def set_values(self, theme_name: str, font_bias: int):
        blocked = self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(theme_name)
        self.theme_combo.blockSignals(blocked)

        blocked = self.font_bias_spin.blockSignals(True)
        self.font_bias_spin.setValue(font_bias)
        self.font_bias_spin.blockSignals(blocked)


class SaveSlotsPane(QFrame):
    slot_requested = Signal(str)
    close_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("saveSlotsPane")
        self.mode = "load"
        self.slot_entries: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title = QLabel("save slots")
        self.title.setObjectName("saveSlotsTitle")
        layout.addWidget(self.title)

        self.note = QLabel("select a session archive")
        self.note.setObjectName("saveSlotsNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("saveSlotsInput")
        self.name_input.setPlaceholderText("session label")
        layout.addWidget(self.name_input)

        self.slot_buttons: dict[str, QPushButton] = {}
        for slot_key in GameState.iter_save_slot_keys():
            button = QPushButton()
            button.setObjectName("saveSlotButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, key=slot_key: self.slot_requested.emit(key))
            layout.addWidget(button)
            self.slot_buttons[slot_key] = button

        self.status = QLabel("")
        self.status.setObjectName("saveSlotsStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.close_button = QPushButton("close")
        self.close_button.setObjectName("settingsReset")
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

    def set_mode(self, mode: str, entries: list[dict], *, default_name: str = "", status: str = ""):
        self.mode = mode
        self.slot_entries = {entry["slot_key"]: entry for entry in entries}
        is_save_mode = mode == "save"

        self.title.setText("save session" if is_save_mode else "load session")
        self.note.setText(
            "choose a manual slot and give this run a label."
            if is_save_mode
            else "choose an autosave or named slot to restore."
        )
        self.name_input.setVisible(is_save_mode)
        if is_save_mode:
            self.name_input.setText(default_name)
            self.name_input.selectAll()
            self.name_input.setFocus()
        else:
            self.name_input.clear()

        for slot_key, button in self.slot_buttons.items():
            entry = self.slot_entries.get(slot_key) or {
                "slot_key": slot_key,
                "exists": False,
                "display_name": GameState.default_slot_label(slot_key),
                "kind": "autosave" if slot_key == GameState.AUTOSAVE_SLOT_KEY else "manual",
            }
            if is_save_mode and slot_key == GameState.AUTOSAVE_SLOT_KEY:
                button.hide()
                continue
            button.show()
            if is_save_mode:
                button.setEnabled(True)
                button.setText(self._format_save_button(entry))
            else:
                button.setEnabled(bool(entry.get("exists")))
                button.setText(self._format_load_button(entry))

        self.status.setText(status)

    def current_label(self) -> str:
        return self.name_input.text().strip()

    def _format_load_button(self, entry: dict) -> str:
        label = entry.get("display_name") or GameState.default_slot_label(entry["slot_key"])
        if not entry.get("exists"):
            return f"{label}\nempty"
        saved_at = entry.get("saved_at") or "unknown time"
        day = entry.get("day")
        handle = entry.get("handle") or "operator"
        trace = entry.get("trace")
        wallet = entry.get("wallet")
        prefix = "autosave" if entry.get("slot_key") == GameState.AUTOSAVE_SLOT_KEY else label
        return (
            f"{prefix}\n"
            f"{handle} // day {day if day is not None else '--'}  wallet {wallet if wallet is not None else '--'}c  "
            f"trace {trace if trace is not None else '--'}\n"
            f"{saved_at}"
        )

    def _format_save_button(self, entry: dict) -> str:
        label = GameState.default_slot_label(entry["slot_key"])
        if not entry.get("exists"):
            return f"{label}\nwrite new save here"
        saved_at = entry.get("saved_at") or "unknown time"
        current_name = entry.get("display_name") or label
        day = entry.get("day")
        return f"{label}\noverwrite {current_name} // day {day if day is not None else '--'}\n{saved_at}"


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
        self.completion_provider = None
        self._completion_cycle_seed = ""
        self._completion_cycle_values: list[str] = []
        self._completion_matches: list[str] = []

    def set_completion_provider(self, provider):
        self.completion_provider = provider
        self.reset_completion_cycle()

    def reset_completion_cycle(self):
        self._completion_cycle_seed = ""
        self._completion_cycle_values = []
        self._completion_matches = []

    def _show_completion_hint(self, matches: list[str]):
        if len(matches) <= 1:
            QToolTip.hideText()
            return
        preview = matches[:12]
        hint = "\n".join(preview)
        if len(matches) > len(preview):
            hint += f"\n... +{len(matches) - len(preview)} more"
        QToolTip.showText(self.mapToGlobal(self.cursorRect().bottomRight()), hint, self)

    def _current_token_bounds(self):
        text = self.current_input
        if not text or text.endswith(" "):
            return len(text), len(text)
        match = re.search(r"\S+$", text)
        if not match:
            return len(text), len(text)
        return match.start(), match.end()

    @staticmethod
    def _common_completion_prefix(matches: list[str]) -> str:
        if not matches:
            return ""
        prefix = matches[0]
        for candidate in matches[1:]:
            limit = min(len(prefix), len(candidate))
            index = 0
            while index < limit and prefix[index] == candidate[index]:
                index += 1
            prefix = prefix[:index]
            if not prefix:
                break
        return prefix

    def apply_tab_completion(self):
        if not callable(self.completion_provider):
            return False

        if self._completion_cycle_values and self.current_input in [self._completion_cycle_seed, *self._completion_cycle_values]:
            if self.current_input == self._completion_cycle_seed:
                next_index = 0
            else:
                current_index = self._completion_cycle_values.index(self.current_input)
                next_index = (current_index + 1) % len(self._completion_cycle_values)
            self.current_input = self._completion_cycle_values[next_index]
            self._sync_view()
            self._show_completion_hint(self._completion_matches)
            return True

        start, end = self._current_token_bounds()
        prefix_text = self.current_input[:start]
        current_token = self.current_input[start:end]
        matches = list(self.completion_provider(self.current_input) or [])
        if not matches:
            self.reset_completion_cycle()
            return False

        common_prefix = self._common_completion_prefix(matches)
        if len(matches) == 1:
            completed = prefix_text + matches[0]
            if not completed.endswith(" "):
                completed += " "
            self.current_input = completed
            self.reset_completion_cycle()
            self._sync_view()
            self._show_completion_hint(matches)
            return True

        if not prefix_text and not current_token:
            self._completion_cycle_seed = self.current_input
            self._completion_cycle_values = [match for match in matches]
            self._completion_matches = matches
            self._show_completion_hint(matches)
            return True

        cycle_values = [prefix_text + match for match in matches]
        if common_prefix and len(common_prefix) > len(current_token):
            self.current_input = prefix_text + common_prefix
            self._completion_cycle_seed = self.current_input
            self._completion_cycle_values = cycle_values
            self._completion_matches = matches
            self._sync_view()
            self._show_completion_hint(matches)
            return True

        cycle_seed = self.current_input
        self.current_input = cycle_values[0]
        self._completion_cycle_seed = cycle_seed
        self._completion_cycle_values = cycle_values
        self._completion_matches = matches
        self._sync_view()
        self._show_completion_hint(matches)
        return True

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
            self.reset_completion_cycle()
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
            self.reset_completion_cycle()
            self._sync_view()
            self.command_submitted.emit("cls")
            return

        if key == Qt.Key.Key_Tab:
            if self.apply_tab_completion():
                return
            event.ignore()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            command = self.current_input
            self.current_input = ""
            self.reset_completion_cycle()
            self._sync_view()
            self.command_submitted.emit(command)
            return

        if key == Qt.Key.Key_Backspace:
            if self.current_input:
                self.current_input = self.current_input[:-1]
                self.reset_completion_cycle()
                self._sync_view()
            return

        if key == Qt.Key.Key_Escape:
            self.current_input = ""
            self.reset_completion_cycle()
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
                    self.reset_completion_cycle()
                    self._sync_view()
            elif copy_match:
                super().keyPressEvent(event)
            return

        if text and text >= " ":
            self.current_input += text
            self.reset_completion_cycle()
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
            (re.compile(r"^(RAM .*)$"), build_char_format(PALETTE["yellow"], bold=True)),
            (re.compile(r"^(STACK DELTA.*|STACK OUTCOME.*)$"), build_char_format(PALETTE["magenta"], bold=True)),
            (re.compile(r"^[A-Z0-9 /:_-]{6,}$"), build_char_format(PALETTE["cyan"], bold=True)),
            (
                re.compile(
                    r"^(HOST|WEAPON|COUNTER|ENTRY|EXPOSURE|INTENT|WEAK POINT|VULN|ADAPT|DEFENSE|CACHE|HANDLE|TITLE|DAY|WALLET|TRACE|RAM|SIGNATURE|ITEMS|LOCAL IP|BOT BAY|CLASS GUIDE|OWNER|ROLE|NETRANGE|OPERATING|INTEL|SUBSYSTEMS|LINK|PORTS|STACK)\b"
                ),
                build_char_format(PALETTE["cyan"], bold=True),
            ),
            (re.compile(r"\b(OS|SEC|NET|MEM|STO)\b"), build_char_format(PALETTE["accent"], bold=True)),
            (re.compile(r"\b(CLEARED|ROOTED|MARKET|LIVE|SCANNED|AVAILABLE|DONE|TRACKING)\b"), build_char_format(PALETTE["green"], bold=True)),
            (re.compile(r"\b(WARM|TRACE|WARNING|ALERT|CONTESTED|BORDER|LOCKDOWN)\b"), build_char_format(PALETTE["yellow"], bold=True)),
            (re.compile(r"\b(HOT|LOCKED|FAILED|BURNED|TERMINATED|BRICKED|INFECTED)\b"), build_char_format(PALETTE["red"], bold=True)),
            (re.compile(r"\b(FORENSIC)\b"), build_char_format(PALETTE["magenta"], bold=True)),
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
        if stripped.startswith("ALERT"):
            self.setFormat(0, len(text), build_char_format(PALETTE["red"], bold=True))
            return
        if stripped.startswith("WARNING"):
            self.setFormat(0, len(text), build_char_format(PALETTE["yellow"], bold=True))
            return
        if stripped.startswith("NOTICE") or stripped.startswith("HOSTILE"):
            self.setFormat(0, len(text), build_char_format(PALETTE["magenta"], bold=True))
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
        self.setProperty("disturbed", False)
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

    def set_disturbed(self, disturbed: bool):
        if self.property("disturbed") != disturbed:
            self.setProperty("disturbed", disturbed)
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
    BOOT_STEP_SECONDS = 0.58
    BOOT_STAGGER_SECONDS = 0.18
    BOOT_HOLD_SECONDS = 0.65

    def __init__(self):
        super().__init__()
        self.backend = PySideGameBackend()
        self.backend.boot_menu = True
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
        self.session_boot_profile: str | None = None
        self.session_boot_started_at: float | None = None
        self.window_boot_started_at: dict[str, float] = {}
        self.tutorial_boot_started = False
        self.tutorial_boot_complete = False
        self.tutorial_boot_step = 0
        self.tutorial_boot_revealed: set[str] = set()
        self.tutorial_warmup_requested = False
        self.tutorial_warmup_gate_pending = False
        self.tutorial_warmup_release_sent = False
        self.tutorial_live_boot_started_at: dict[str, float] = {}
        self.main_menu_active = True
        self.main_menu_pending_choice: str | None = None
        self.save_manager_mode: str | None = None
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
        self.boot_menu.continue_requested.connect(self.open_load_save_manager)
        self.boot_menu.quit_requested.connect(self.close)
        self.boot_menu.show()

        self.shell = TerminalShell()
        self.feed = self.shell.feed
        self.input = self.feed
        self.feed.command_submitted.connect(self.submit_command)
        self.feed.set_completion_provider(self.get_live_terminal_completions)
        self.feed_highlighter = FeedHighlighter(self.feed.document())
        self.log_archive = LiveLogPane()

        self.player = TerminalPane()
        self.target = TerminalPane()
        self.objective = ObjectivePane(self.open_tutorial_window)
        self.route = RouteMapPane(self.route_node_label, self.backend.get_node_status_text, self.backend.build_node_intel_summary)
        self.databank = DatabankPane(self.lookup_databank_entry, self.open_databank_entry)
        self.dev_shell = TerminalShell()
        self.dev_feed = self.dev_shell.feed
        self.dev_input = self.dev_feed
        self.dev_feed.command_submitted.connect(self.submit_dev_command)
        self.dev_feed.set_completion_provider(self.get_dev_terminal_completions)
        self.dev_feed_highlighter = FeedHighlighter(self.dev_feed.document())
        self.settings = SettingsPane()
        self.save_slots = SaveSlotsPane()
        self.payload_detail = TerminalPane()
        self.tutorial_detail = TutorialPane()
        self.tutorial_detail.clicked.connect(self.handle_tutorial_click)
        self.panel_highlighters = [
            PanelHighlighter(self.player.body.document()),
            PanelHighlighter(self.target.body.document()),
            PanelHighlighter(self.objective.body.document()),
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
        self.create_window("saves", self.save_slots, "save slots", show=False)
        self.create_window("payload", self.payload_detail, "payload", show=False)
        self.create_window("tutorial", self.tutorial_detail, "tutorial coach", show=False)

        self.settings.theme_changed.connect(self.change_color_scheme)
        self.settings.font_bias_changed.connect(self.change_font_bias)
        self.settings.reset_requested.connect(self.reset_display_settings)
        self.settings.save_slots_requested.connect(self.open_save_save_manager)
        self.settings.exit_to_menu_requested.connect(self.return_to_main_menu)
        self.settings.set_values(self.color_scheme_name, self.font_size_bias)
        self.save_slots.slot_requested.connect(self.handle_save_slot_requested)
        self.save_slots.close_requested.connect(self.close_save_manager)

        for key in ["terminal", "log", "player", "target", "objective", "route", "databank", "dev", "settings", "saves", "payload", "tutorial"]:
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
        window.hidden_from_ui.connect(lambda _key, name=key: self.on_window_hidden(name))
        window.shown_from_ui.connect(lambda _key: self.refresh_taskbar())
        self.floating_windows[key] = window
        if show:
            window.show()
            self.taskbar_seen_keys.add(key)
        else:
            window.hide()

    def on_window_hidden(self, key: str):
        if key == "saves":
            self.save_manager_mode = None
        self.refresh_taskbar()

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
            "saves": PALETTE["cyan"],
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
        self.layout_save_manager()
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

    def layout_save_manager(self):
        window = self.floating_windows.get("saves")
        if not window:
            return
        rect = self.desktop.rect().adjusted(28, 28, -28, -28)
        width = max(430, min(620, rect.width() // 2))
        height = max(340, min(500, rect.height() // 2))
        x = rect.left() + max(18, (rect.width() - width) // 2)
        y = rect.top() + max(18, (rect.height() - height) // 3)
        window.is_maximized_window = False
        window.header.max_button.setText("[]")
        window.setGeometry(x, y, width, height)
        window._normal_geometry = window.geometry()
        window.clamp_to_desktop()

    def update_main_menu_state(self):
        save_available = any(entry.get("exists") for entry in GameState.list_save_slots())
        self.boot_menu.set_continue_available(save_available)
        if not self.main_menu_pending_choice:
            self.boot_menu.set_busy(False, status=self.boot_menu.status.text())

    def apply_main_menu_visibility(self):
        for key, window in self.floating_windows.items():
            if key == "saves" and self.save_manager_mode == "load":
                continue
            window.hide()
        self.boot_menu.show()
        self.boot_menu.raise_()
        if self.save_manager_mode == "load":
            window = self.floating_windows.get("saves")
            if window:
                window.show()
                window.raise_()
        self.dock.hide()

    def show_main_menu(self):
        self.main_menu_active = True
        self.main_menu_pending_choice = None
        self.close_save_manager()
        self.update_main_menu_state()
        self.layout_boot_menu()
        self.apply_main_menu_visibility()

    def hide_main_menu(self):
        self.main_menu_active = False
        self.main_menu_pending_choice = None
        self.boot_menu.set_busy(False)
        self.boot_menu.hide()
        self.close_save_manager()
        self.dock.show()
        self.reset_window_layout()

    def dismiss_main_menu_for_tutorial_loading(self):
        self.main_menu_active = False
        self.main_menu_pending_choice = None
        self.boot_menu.set_busy(False)
        self.boot_menu.hide()
        self.dock.hide()
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.hide()
        tutorial_window = self.floating_windows.get("tutorial")
        if tutorial_window:
            tutorial_window.hide()
        if self.backend.objective_is_tutorial:
            self.sync_tutorial_overlay(force_show=True)
        self.refresh_taskbar()

    def dismiss_main_menu_for_standard_loading(self):
        self.main_menu_active = False
        pending_choice = self.main_menu_pending_choice
        self.boot_menu.set_busy(False)
        self.boot_menu.hide()
        self.dock.hide()
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.hide()
        self.main_menu_pending_choice = pending_choice
        self.refresh_taskbar()

    def submit_main_menu_choice(self, choice: str):
        self.main_menu_pending_choice = choice
        loading_copy = get_boot_menu_loading_copy(choice)
        self.boot_menu.set_busy(True, subtitle=loading_copy[0], status=loading_copy[1])
        self.layout_boot_menu()
        self.apply_main_menu_visibility()
        self.backend.input_queue.put(choice)

    def open_load_save_manager(self):
        entries = GameState.list_save_slots()
        self.save_manager_mode = "load"
        self.save_slots.set_mode("load", entries, status="choose an autosave or named slot to continue.")
        self.layout_save_manager()
        window = self.floating_windows["saves"]
        window.show()
        window.raise_()
        self.apply_main_menu_visibility()
        self.refresh_taskbar()

    def open_save_save_manager(self):
        if not self.backend.state or not self.backend.player:
            return
        settings_window = self.floating_windows.get("settings")
        if settings_window and settings_window.isVisible():
            settings_window.hide_window()
        default_name = ""
        state = self.backend.state
        player = self.backend.player
        if state and player:
            default_name = f"{player.handle} // day {state.day}"
        entries = GameState.list_save_slots()
        self.save_manager_mode = "save"
        self.save_slots.set_mode("save", entries, default_name=default_name, status="pick a slot to write this run.")
        self.layout_save_manager()
        window = self.floating_windows["saves"]
        window.show()
        window.raise_()
        self.activate_window("saves")
        self.refresh_taskbar()

    def close_save_manager(self):
        self.save_manager_mode = None
        window = self.floating_windows.get("saves")
        if window:
            window.hide()
        self.refresh_taskbar()

    def handle_save_slot_requested(self, slot_key: str):
        if self.save_manager_mode == "load":
            self.backend.selected_save_reference = slot_key
            self.close_save_manager()
            self.submit_main_menu_choice("3")
            return

        if self.save_manager_mode == "save":
            label = self.save_slots.current_label()
            try:
                self.backend.write_named_save(slot_key, label)
            except Exception as exc:
                self.save_slots.status.setText(f"save failed: {exc}")
                return
            saved_name = (label or GameState.default_slot_label(slot_key)).strip()
            self.save_slots.status.setText(f"{saved_name} written successfully.")
            self.update_main_menu_state()
            self.close_save_manager()

    def return_to_main_menu(self):
        if self.main_menu_active:
            return
        settings_window = self.floating_windows.get("settings")
        if settings_window and settings_window.isVisible():
            settings_window.hide_window()
        self.close_save_manager()
        self.clear_boot_sequence()
        self.main_menu_active = True
        self.main_menu_pending_choice = None
        self.boot_menu.set_busy(
            True,
            subtitle="closing live session",
            status="writing checkpoint and returning to the boot menu...",
        )
        self.layout_boot_menu()
        self.apply_main_menu_visibility()
        self.backend.request_return_to_main_menu()

    def clear_boot_sequence(self):
        self.session_boot_profile = None
        self.session_boot_started_at = None
        self.window_boot_started_at = {}

    def clear_tutorial_live_boot_sequence(self):
        self.tutorial_live_boot_started_at = {}

    def start_standard_boot_sequence(self):
        self.session_boot_profile = "standard"
        self.session_boot_started_at = monotonic()
        self.window_boot_started_at = {}
        self.clear_tutorial_live_boot_sequence()
        self.dock.hide()
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.hide()

    def is_standard_boot_active(self) -> bool:
        return self.session_boot_profile == "standard" and self.session_boot_started_at is not None

    def mark_window_boot_started(self, key: str):
        if key not in self.primary_window_keys:
            return
        self.window_boot_started_at.setdefault(key, monotonic())

    def standard_boot_has_window_started(self, key: str) -> bool:
        if not self.is_standard_boot_active():
            return False
        if key not in self.primary_window_keys or self.session_boot_started_at is None:
            return False
        start_time = self.session_boot_started_at + (self.primary_window_keys.index(key) * self.BOOT_STAGGER_SECONDS)
        return monotonic() >= start_time

    def start_tutorial_live_boot_sequence(self):
        started = monotonic()
        self.tutorial_live_boot_started_at = {
            "objective": started,
            "player": started + 0.18,
            "target": started + 0.36,
            "route": started + 0.54,
            "databank": started + 0.72,
            "log": started + 0.90,
        }

    def get_tutorial_live_boot_stage(self, key: str) -> int | None:
        if not self.backend.objective_is_tutorial:
            return None
        start_time = self.tutorial_live_boot_started_at.get(key)
        if start_time is None:
            return None
        _label, commands = get_window_boot_sequence(key)
        total_stages = len(commands) + 2
        elapsed = monotonic() - start_time
        if elapsed < 0:
            return None
        max_duration = total_stages * self.BOOT_STEP_SECONDS + self.BOOT_HOLD_SECONDS
        if elapsed > max_duration:
            return None
        return min(total_stages - 1, int(elapsed / self.BOOT_STEP_SECONDS))

    def get_window_boot_stage(self, key: str) -> int | None:
        if key not in self.primary_window_keys:
            return None
        if self.session_boot_profile not in {"standard", "tutorial"}:
            return None
        _label, commands = get_window_boot_sequence(key)
        total_stages = len(commands) + 2
        if self.session_boot_profile == "standard":
            if self.session_boot_started_at is None:
                return None
            start_time = self.session_boot_started_at + (self.primary_window_keys.index(key) * self.BOOT_STAGGER_SECONDS)
        else:
            start_time = self.window_boot_started_at.get(key)
            if start_time is None:
                return None
        elapsed = monotonic() - start_time
        if elapsed < 0:
            return None
        max_duration = total_stages * self.BOOT_STEP_SECONDS + self.BOOT_HOLD_SECONDS
        if elapsed > max_duration:
            return None
        return min(total_stages - 1, int(elapsed / self.BOOT_STEP_SECONDS))

    def get_window_boot_text(self, key: str) -> str | None:
        stage = self.get_window_boot_stage(key)
        if stage is None:
            stage = self.get_tutorial_live_boot_stage(key)
        if stage is None:
            return None
        return build_window_boot_text(key, stage)

    def get_window_boot_snapshot(self, key: str) -> list[tuple[str, str]] | None:
        stage = self.get_window_boot_stage(key)
        if stage is None:
            stage = self.get_tutorial_live_boot_stage(key)
        if stage is None:
            return None
        return build_window_boot_snapshot(key, stage)

    def is_any_window_booting(self) -> bool:
        return any(self.get_window_boot_stage(key) is not None for key in self.primary_window_keys)

    def settle_boot_sequence(self):
        was_standard = self.session_boot_profile == "standard"
        if self.session_boot_profile and not self.is_any_window_booting():
            self.clear_boot_sequence()
            if was_standard and not self.main_menu_active:
                self.dock.show()
                for key in self.primary_window_keys:
                    window = self.floating_windows.get(key)
                    if window:
                        window.show()
                self.activate_window("terminal")
                self.refresh_taskbar()
        if self.tutorial_live_boot_started_at:
            active = False
            for key in tuple(self.tutorial_live_boot_started_at):
                if self.get_tutorial_live_boot_stage(key) is not None:
                    active = True
            if not active:
                self.clear_tutorial_live_boot_sequence()

    def reset_window_layout(self):
        if self.main_menu_active:
            self.apply_main_menu_visibility()
            return
        rect = self.desktop.rect().adjusted(18, 18, -18, -18)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        gap = 14
        top_h = max(148, int(rect.height() * 0.18))
        bottom_h = rect.height() - top_h - gap

        side_w = max(440, int(rect.width() * 0.39))
        if rect.width() - side_w - gap < 560:
            side_w = max(380, int(rect.width() * 0.35))
        terminal_w = rect.width() - side_w - gap
        left_top_w = terminal_w
        objective_w = max(250, int(left_top_w * 0.34))
        databank_w = left_top_w - objective_w - gap
        log_h = max(170, int(bottom_h * 0.26))
        terminal_h = max(260, bottom_h - log_h - gap)
        route_h = max(230, int(bottom_h * 0.31))
        target_h = max(220, bottom_h - route_h - gap)
        tutorial_boot_active = self.is_tutorial_boot_active()
        standard_boot_active = self.is_standard_boot_active()

        self._place_window("objective", rect.left(), rect.top(), objective_w, top_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("databank", rect.left() + objective_w + gap, rect.top(), databank_w, top_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("player", rect.left() + terminal_w + gap, rect.top(), side_w, top_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("terminal", rect.left(), rect.top() + top_h + gap, terminal_w, terminal_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("log", rect.left(), rect.top() + top_h + gap + terminal_h + gap, terminal_w, log_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("target", rect.left() + terminal_w + gap, rect.top() + top_h + gap, side_w, target_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)
        self._place_window("route", rect.left() + terminal_w + gap, rect.top() + top_h + gap + target_h + gap, side_w, route_h, tutorial_boot=tutorial_boot_active, standard_boot=standard_boot_active)

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
        elif standard_boot_active:
            self.apply_standard_boot_visibility()
        else:
            self.activate_window("terminal")
        self.refresh_taskbar()

    def _place_window(self, key: str, x: int, y: int, width: int, height: int, *, tutorial_boot: bool = False, standard_boot: bool = False):
        window = self.floating_windows[key]
        window.is_maximized_window = False
        window._normal_geometry = QRect(x, y, width, height)
        window.setGeometry(x, y, width, height)
        window.header.max_button.setText("[]")
        if tutorial_boot:
            should_show = key in self.tutorial_boot_revealed
        elif standard_boot:
            should_show = self.standard_boot_has_window_started(key)
        else:
            should_show = True
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
        self.clear_boot_sequence()
        self.clear_tutorial_live_boot_sequence()
        self.session_boot_profile = "tutorial"
        self.tutorial_boot_started = True
        self.tutorial_boot_complete = False
        self.tutorial_boot_step = 0
        self.tutorial_boot_revealed = set()
        self.tutorial_warmup_requested = False
        self.tutorial_warmup_gate_pending = False
        self.tutorial_warmup_release_sent = False
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if window:
                window.hide()
        self.refresh_taskbar()

    def finish_tutorial_boot_sequence(self):
        self.tutorial_boot_complete = True
        self.tutorial_boot_revealed = set(self.primary_window_keys)
        self.tutorial_warmup_gate_pending = True
        self.tutorial_warmup_requested = False
        self.tutorial_warmup_release_sent = False
        for key in self.primary_window_keys:
            self.mark_window_boot_started(key)
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
                self.mark_window_boot_started(key)
                window.show()
            else:
                window.hide()
        tutorial_window = self.floating_windows.get("tutorial")
        if tutorial_window:
            tutorial_window.show()
            tutorial_window.raise_()

    def apply_standard_boot_visibility(self):
        if not self.is_standard_boot_active():
            return
        for key in self.primary_window_keys:
            window = self.floating_windows.get(key)
            if not window:
                continue
            if self.standard_boot_has_window_started(key):
                window.show()
                window.raise_()
            else:
                window.hide()

    def handle_tutorial_click(self):
        if not self.is_tutorial_boot_active():
            if self.is_tutorial_warmup_gate_active():
                if not self.tutorial_warmup_requested:
                    self.tutorial_warmup_requested = True
                    self.sync_tutorial_overlay(force_show=True)
                    if self.backend.active_prompt and not self.tutorial_warmup_release_sent:
                        self.tutorial_warmup_release_sent = True
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
            self.databank.body,
            self.payload_detail.body,
            self.tutorial_detail.body,
        ]:
            widget.setFont(mono_font)

        self.route.canvas.setFont(mono_font)

        for widget in [
            self.settings,
            self.settings.title,
            self.settings.note,
            self.settings.theme_combo,
            self.settings.font_bias_spin,
            self.settings.reset_button,
            self.settings.save_button,
            self.settings.exit_button,
            self.save_slots,
            self.save_slots.title,
            self.save_slots.note,
            self.save_slots.name_input,
            self.save_slots.status,
            self.save_slots.close_button,
        ]:
            widget.setFont(ui_font)

        for button in self.save_slots.slot_buttons.values():
            button.setFont(ui_font)

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
            QFrame#saveSlotsPane {{
                background: transparent;
            }}
            QLabel#settingsTitle {{
                color: {PALETTE["white"]};
                font-weight: 700;
            }}
            QLabel#settingsNote {{
                color: {PALETTE["muted"]};
            }}
            QLabel#saveSlotsTitle {{
                color: {PALETTE["white"]};
                font-weight: 700;
            }}
            QLabel#saveSlotsNote {{
                color: {PALETTE["muted"]};
            }}
            QLabel#saveSlotsStatus {{
                color: {PALETTE["cyan"]};
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
            QLineEdit#saveSlotsInput {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 7px;
                background: {PALETTE["terminal_alt"]};
                color: {PALETTE["text"]};
                padding: 6px 8px;
                min-height: 30px;
            }}
            QLineEdit#saveSlotsInput:focus {{
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
            QPushButton#saveSlotButton {{
                border: 1px solid {PALETTE["panel_border"]};
                border-radius: 8px;
                background: {PALETTE["terminal_alt"]};
                color: {PALETTE["text"]};
                padding: 9px 10px;
                text-align: left;
            }}
            QPushButton#saveSlotButton:hover {{
                border-color: {PALETTE["panel_border_active"]};
                background: {PALETTE["accent_soft"]};
            }}
            QPushButton#saveSlotButton:disabled {{
                color: {PALETTE["muted"]};
                border-color: {PALETTE["panel_border"]};
                background: rgba(16, 22, 33, 0.85);
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
            QFrame#floatingWindow[disturbed="true"] {{
                border-color: #8a3942;
                background: #19131a;
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
            QFrame#floatingWindow[disturbed="true"] QFrame#windowHeader {{
                background: #2a151b;
                border-bottom: 1px solid #a54b57;
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
            self.route.canvas,
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

    @staticmethod
    def filter_completion_matches(candidates, prefix: str):
        lowered_prefix = (prefix or "").lower()
        seen = set()
        matches = []
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in seen:
                continue
            if lowered_prefix and not str(candidate).lower().startswith(lowered_prefix):
                continue
            seen.add(candidate)
            matches.append(candidate)
        exact = lowered_prefix
        return sorted(matches, key=lambda value: (str(value).lower() != exact, str(value).lower()))

    @staticmethod
    def split_completion_input(text: str):
        raw = text or ""
        parts = raw.split()
        if raw.endswith(" "):
            parts.append("")
        return parts

    def get_live_terminal_completions(self, text: str):
        return self.backend.get_terminal_completion_matches(text)

    def get_dev_terminal_completions(self, text: str):
        parts = self.split_completion_input(text)
        token = parts[-1] if parts else ""

        installed_scripts = sorted((self.backend.arsenal.scripts if self.backend.arsenal else {}).keys())
        installed_flags = sorted((self.backend.arsenal.flags if self.backend.arsenal else {}).keys())
        all_items = sorted((self.backend.item_library or {}).keys())
        route_ips = self.backend.get_route_completion_node_ids()
        window_names = sorted({"terminal", "log", "player", "target", "objective", "route", "databank", "dev", "settings", "saves", "payload", "tutorial"})

        if len(parts) <= 1:
            roots = [
                "help",
                "status",
                "save",
                "dump",
                "set",
                "hp",
                "grant",
                "revoke",
                "give",
                "take",
                "reveal",
                "conceal",
                "route",
                "window",
                "layout",
                "clear",
                "cls",
                "close",
                "exit",
                "quit",
            ]
            return self.filter_completion_matches(roots, token)

        name = parts[0].lower()
        if name == "dump":
            return self.filter_completion_matches(
                ["player", "target", "objective", "route", "world", "databank", "log", "state", "contracts", "history"],
                token,
            )
        if name == "set":
            return self.filter_completion_matches(["day", "crypto", "trace", "ram", "maxram"], token)
        if name == "hp":
            if len(parts) == 2:
                return self.filter_completion_matches(["player", "target"], token)
            if len(parts) == 3:
                return self.filter_completion_matches(self.backend.get_completion_subsystem_tokens(), token.upper())
            return []
        if name in {"grant", "revoke"}:
            if len(parts) == 2:
                return self.filter_completion_matches(["script", "flag"], token)
            if len(parts) == 3 and parts[1].lower() == "script":
                return self.filter_completion_matches(installed_scripts, token)
            if len(parts) == 3 and parts[1].lower() == "flag":
                return self.filter_completion_matches(installed_flags, token)
            return []
        if name in {"give", "take"}:
            if len(parts) == 2:
                return self.filter_completion_matches(["item"], token)
            if len(parts) == 3 and parts[1].lower() == "item":
                return self.filter_completion_matches(all_items, token)
            if len(parts) == 4 and parts[1].lower() == "item":
                return self.filter_completion_matches(["1", "2", "3", "4", "5", "10"], token)
            return []
        if name in {"reveal", "conceal"}:
            if len(parts) == 2:
                return self.filter_completion_matches(["target"], token)
            if len(parts) == 3 and parts[1].lower() == "target":
                return self.filter_completion_matches(["surface", "identity", "weapon", "telemetry", "intent", "weakness", "all"], token)
            return []
        if name == "route":
            if len(parts) == 2:
                return self.filter_completion_matches(["clear", "reopen", "activate"], token)
            if len(parts) == 3 and parts[1].lower() in {"clear", "reopen", "activate"}:
                return self.filter_completion_matches([*route_ips, "active"], token)
            return []
        if name == "window":
            if len(parts) == 2:
                return self.filter_completion_matches(["list", "open", "close", "focus"], token)
            if len(parts) == 3 and parts[1].lower() in {"open", "close", "focus"}:
                return self.filter_completion_matches(window_names, token)
            return []
        if name == "layout":
            return self.filter_completion_matches(["reset"], token)
        return []

    def refresh_from_backend(self):
        bootloader_prompt = self.backend.active_prompt.strip().lower().startswith("select an option:")
        if bootloader_prompt and not self.main_menu_active and not self.main_menu_pending_choice:
            self.show_main_menu()
        elif bootloader_prompt and self.main_menu_active and not self.main_menu_pending_choice:
            self.update_main_menu_state()

        self.refresh_log()
        self.refresh_top_bar()
        self.refresh_windows()
        self.refresh_dev_console()

        if not self.main_menu_active and self.backend.consume_dev_console_request():
            self.open_dev_console()

        if self.main_menu_active and self.main_menu_pending_choice:
            if self.main_menu_pending_choice == "1":
                if self.backend.objective_is_tutorial:
                    self.hide_main_menu()
                    self.clear_boot_sequence()
            elif self.backend.state is not None and not self.backend.objective_is_tutorial and not bootloader_prompt:
                if not self.is_standard_boot_active():
                    self.dismiss_main_menu_for_standard_loading()
                    self.start_standard_boot_sequence()
                    self.reset_window_layout()

        if self.is_standard_boot_active():
            self.apply_standard_boot_visibility()

        self.refresh_prompt_bar()
        self.refresh_taskbar()
        self.settle_boot_sequence()

        if self.backend.game_thread and not self.backend.game_thread.is_alive() and not self.backend.running:
            self.close()

    def refresh_all(self):
        self.refresh_top_bar()
        self.refresh_windows()
        self.refresh_dev_console()
        self.refresh_prompt_bar()
        self.refresh_taskbar()

    def refresh_log(self):
        boot_snapshot = self.get_window_boot_snapshot("terminal")
        if boot_snapshot is not None:
            if self.feed.set_history(boot_snapshot):
                self.feed_highlighter.set_line_tones([tone for _line, tone in boot_snapshot])
                self._last_log_snapshot = boot_snapshot
            return
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

        if self.session_boot_profile == "standard" and self.is_any_window_booting():
            self.brand_label.setText("terminal rogue")
            self.session_label.setText("root@bootstrap:/sbin/session-init")
            self.day_chip.set_value("--")
            self.day_chip.set_kind("accent")
            self.wallet_chip.set_value("--")
            self.wallet_chip.set_kind("accent")
            self.trace_chip.set_value("--")
            self.trace_chip.set_kind("accent")
            self.sweep_chip.set_value("--")
            self.sweep_chip.set_kind("accent")
            self.status_chip.set_value("bringing windows online")
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
        active = self.get_runtime_status_override() or self.backend.map_status or "idle shell"
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

    def get_runtime_disturbance_map(self) -> dict[str, list[tuple[str, str]]]:
        engine = getattr(self.backend, "combat_engine", None)
        if not engine:
            return {}
        with self.backend.io_lock:
            return {
                key: list(value)
                for key, value in getattr(engine, "ui_window_disturbances", {}).items()
            }

    def get_runtime_status_override(self) -> str:
        engine = getattr(self.backend, "combat_engine", None)
        if not engine:
            return ""
        with self.backend.io_lock:
            return str(getattr(engine, "ui_status_override", "") or "")

    def append_runtime_disturbance(self, key: str, text: str) -> str:
        disturbances = self.get_runtime_disturbance_map()
        lines = disturbances.get(key, [])
        if not lines:
            return text
        block = "\n".join(line for line, _tone in lines)
        if not text.strip():
            return block
        return text.rstrip() + "\n\n" + block

    def refresh_windows(self):
        self.set_window_title("terminal", self.backend.format_pane_title(self.backend.get_shell_cwd()))
        self.set_window_title("log", self.backend.format_pane_title("~/var/log/session.log"))
        self.set_window_title("player", self.backend.format_pane_title("~/proc/player"))
        self.set_window_title("target", self.backend.format_pane_title("~/proc/target"))
        self.set_window_title("objective", self.backend.format_pane_title("~/proc/objective"))
        self.set_window_title("settings", self.backend.format_pane_title("~/usr/share/settings"))
        self.set_window_title("saves", self.backend.format_pane_title("~/var/lib/saves"))
        self.set_window_title("dev", self.backend.format_pane_title("~/usr/local/devshell"))
        self.set_window_title("route", self.backend.format_pane_title("~/net/routeweb"))
        self.set_window_title("databank", self.backend.format_pane_title("~/usr/share/databank"))

        disturbance_keys = set(self.get_runtime_disturbance_map())
        pulse_on = int(monotonic() * 4) % 2 == 0
        for name, window in self.floating_windows.items():
            window.set_disturbed(name in disturbance_keys and pulse_on)

        self.player.set_text(self.build_player_text())
        self.target.set_text(self.build_target_text())
        self.objective.set_text(self.build_objective_text())
        self.route.set_network_state(
            self.backend.map_world,
            self.backend.map_cleared,
            self.backend.map_active,
            self.backend.map_status,
            staging=self.is_tutorial_staging_state() or self.get_window_boot_text("route") is not None,
            staging_text=self.build_route_text(),
        )
        self.log_archive.set_text(self.build_log_text())
        self.databank.set_text(self.build_databank_text())
        self.sync_tutorial_overlay()

    def set_window_title(self, key: str, title: str):
        window = self.floating_windows.get(key)
        if window:
            window.set_title(title)

    def lookup_databank_entry(self, raw_line: str):
        line = raw_line.strip()
        if not line or line in {"TOOLS", "FLAGS", "ITEMS", "TARGETS", "MARKET"}:
            return None
        if (
            line.upper().startswith("NAME")
            or line.upper().startswith("FLAG")
            or line.upper().startswith("ITEM")
            or line.upper().startswith("TARGET")
            or line.upper().startswith("SLOT")
        ):
            return None

        token = line.split()[0]
        shop_entries = getattr(self.backend, "shop_databank_entries", {}) or {}
        if token in shop_entries:
            return shop_entries[token]
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
            "domains": self.backend.build_shell_domains_text,
            "history": self.build_dev_history_text,
        }
        builder = mapping.get(topic)
        return builder() if builder else None

    def build_dev_state_text(self) -> str:
        state = self.backend.state
        if not state:
            return "state unavailable"
        tracked = len(state.get_accepted_contracts())
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
            f"inbox           {len(state.current_contracts)} waiting",
            f"contracts       {tracked} tracked / {len(state.contract_history)} archived",
            f"modules         {sum(state.module_inventory.values())} cached / {len(state.rooted_domains)} rooted",
        ]
        if state.active_network:
            lines.extend(
                [
                    f"network         {state.active_network.name}",
                    f"domain          {state.current_domain_id or 'none'}",
                    f"subnet          {state.current_subnet_id or 'none'}",
                ]
            )
        return "\n".join(lines)

    def build_dev_contract_text(self) -> str:
        state = self.backend.state
        if not state:
            return "contracts // state unavailable"
        tracked = state.get_accepted_contracts()
        inbox = list(state.current_contracts)
        if not tracked and not inbox:
            return "contracts // none active"
        lines = ["contracts", ""]
        if tracked:
            lines.append("[tracking]")
            for contract in tracked:
                status = self.backend.get_contract_status(contract)
                lines.append(f"{status:<9} {contract['target_ip']}  {contract['subject']}")
            lines.append("")
        if inbox:
            lines.append("[inbox]")
        for contract in inbox:
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

    @staticmethod
    def describe_module_effects(data: dict, quantity: int = 1) -> list[str]:
        effect = str(data.get("effect", "module")).replace("_", " ")
        amount = data.get("amount")
        lines = [f"installs {effect} infrastructure"]
        if amount:
            lines.append(f"payload amount {amount}")
        if quantity > 1:
            lines.append(f"package quantity {quantity}")
        return lines

    @staticmethod
    def describe_shop_offer_effects(offer: dict, backend) -> list[str]:
        stock_kind = offer.get("stock_kind", offer.get("type", "unknown"))
        arsenal = getattr(backend, "arsenal", None)
        if stock_kind == "script" and arsenal:
            script_id = offer.get("script_id")
            return script_effect_lines(script_id, arsenal.scripts.get(script_id, {}))
        if stock_kind == "flag" and arsenal:
            flag_id = offer.get("flag_id")
            return flag_effect_lines(flag_id, arsenal.flags.get(flag_id, {}))
        if stock_kind == "consumable":
            item_ref = offer.get("item_id")
            item_data = offer.get("consumable_library", {}).get(item_ref, {})
            return item_effect_lines(item_data)
        if stock_kind == "module":
            module_id = offer.get("module_id")
            module_data = offer.get("module_library", {}).get(module_id, {})
            return TerminalRoguePySideWindow.describe_module_effects(module_data, offer.get("quantity", 1))
        if stock_kind == "heal":
            return [f"restores {offer.get('amount', 0)} core OS"]
        if stock_kind == "ram":
            return [f"adds {offer.get('amount', 0)} max RAM permanently", "fully restores live RAM after install"]
        if stock_kind == "trace":
            return [f"reduces trace by {offer.get('amount', 0)}"]
        if stock_kind == "bot":
            return [
                f"installs a support bot with {offer.get('ram_reservation', 1)} reserved RAM",
                f"payload RAM cap {offer.get('script_ram_cap', 2)}",
                f"fires every {offer.get('cadence', 2)} turns",
            ]
        return ["market package"]

    @staticmethod
    def describe_shop_offer(offer: dict, backend) -> str:
        stock_kind = offer.get("stock_kind", offer.get("type", "unknown"))
        arsenal = getattr(backend, "arsenal", None)
        if stock_kind == "script" and arsenal:
            return arsenal.scripts.get(offer.get("script_id"), {}).get("description", "Market script package.")
        if stock_kind == "flag" and arsenal:
            return arsenal.flags.get(offer.get("flag_id"), {}).get("description", "Market modifier package.")
        if stock_kind == "consumable":
            item_data = offer.get("consumable_library", {}).get(offer.get("item_id"), {})
            return item_data.get("description", "One-use field package.")
        if stock_kind == "module":
            module_data = offer.get("module_library", {}).get(offer.get("module_id"), {})
            return module_data.get("description", "Rooted node infrastructure package.")
        if stock_kind == "heal":
            return f"Kernel patch bundle. Restores {offer.get('amount', 0)} Core OS."
        if stock_kind == "ram":
            return f"Hardware overclock package. Adds {offer.get('amount', 0)} permanent max RAM."
        if stock_kind == "trace":
            return f"Trace scrubber pass. Burns off {offer.get('amount', 0)} trace from your current signature."
        if stock_kind == "bot":
            return "Support chassis. Installs a lightweight automation bot into your rig."
        return "Black market package."

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

        if kind == "shop_offer":
            stock_kind = data.get("stock_kind", data.get("type", "unknown"))
            lines.extend(
                [
                    "SYNOPSIS",
                    f" buy {data.get('offer_id', item_id)}",
                    "",
                    "PROFILE",
                    f" market price   {data.get('cost', 0)} crypto",
                    f" stock class    {stock_kind}",
                ]
            )
            if stock_kind == "script":
                script_id = data.get("script_id")
                script_data = self.backend.arsenal.scripts.get(script_id, {}) if self.backend.arsenal else {}
                allowed_flags = self.backend.arsenal.get_owned_allowed_flags(script_id, self.backend.player) if self.backend.arsenal else []
                lines.extend(
                    [
                        f" script         {script_id}",
                        f" ram cost       {script_data.get('ram', 0)}",
                        f" class          {str(script_data.get('type', 'tool')).replace('_', '-')}",
                        f" targeting      {str(script_data.get('default_target')).upper() if script_data.get('default_target') else ('manual or script-defined' if script_data.get('supports_target', True) else 'fixed-domain only')}",
                        f" supports       {', '.join(allowed_flags) or 'none'}",
                    ]
                )
            elif stock_kind == "flag":
                flag_id = data.get("flag_id")
                flag_data = self.backend.arsenal.flags.get(flag_id, {}) if self.backend.arsenal else {}
                lines.extend(
                    [
                        f" flag           {flag_id}",
                        f" ram cost       +{flag_data.get('ram', 0)}",
                        " class          modifier",
                    ]
                )
            elif stock_kind == "consumable":
                lines.extend(
                    [
                        f" package        {data.get('item_id', item_id)} x{data.get('quantity', 1)}",
                        " class          consumable",
                    ]
                )
            elif stock_kind == "module":
                lines.extend(
                    [
                        f" package        {data.get('module_id', item_id)} x{data.get('quantity', 1)}",
                        " class          module",
                    ]
                )
            elif stock_kind == "bot":
                lines.extend(
                    [
                        f" reserve        {data.get('ram_reservation', 1)} RAM",
                        f" payload cap    {data.get('script_ram_cap', 2)} RAM",
                        f" cadence        {data.get('cadence', 2)} turns",
                    ]
                )
            elif stock_kind in {"heal", "ram", "trace"}:
                lines.append(f" payload amount {data.get('amount', 0)}")
            description = self.describe_shop_offer(data, self.backend)
            effects = self.describe_shop_offer_effects(data, self.backend)
        elif kind == "script":
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
        elif kind != "shop_offer":
            description = data.get("description", "No description loaded.")
        lines.extend(["", "DESCRIPTION", f" {description}"])
        if effects:
            lines.extend(["", "EFFECTS"])
            for effect in effects:
                lines.append(f" - {effect}")
        return "\n".join(lines)

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
        boot_locked = self.get_window_boot_stage("terminal") is not None
        tutorial_gate_locked = self.is_tutorial_boot_active() or self.is_tutorial_warmup_gate_active() or boot_locked
        prompt = ""
        if not self.is_tutorial_warmup_gate_active() and not boot_locked:
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
        boot_text = self.get_window_boot_text("objective")
        if boot_text is not None:
            return boot_text
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
        if self.backend.state:
            active_contract_lines = self.backend.state.get_active_contract_summary_lines(limit=4)
            if active_contract_lines:
                lines.extend(["", *active_contract_lines])
        return "\n".join(lines)

    def build_player_text(self) -> str:
        boot_text = self.get_window_boot_text("player")
        if boot_text is not None:
            return boot_text
        if self.is_tutorial_staging_state():
            return player_staging_text()
        with self.backend.io_lock:
            player = self.backend.player
            state = self.backend.state
            projection = None
            if getattr(self.backend, "combat_engine", None):
                snapshot = getattr(self.backend.combat_engine, "planning_snapshot", None)
                if snapshot:
                    projection = snapshot.get("projection")
        if not player or not state:
            return "bootstrapping session state..."

        ram_max = player.get_effective_max_ram()
        ram_regen = player.get_ram_regen()
        stack_detail_line = None
        stack_outcome_line = None
        if projection and projection.projected_player and projection.steps:
            ghost_player = projection.projected_player
            legality = "legal" if projection.legal else "fault"
            ram_delta = ghost_player.current_ram - player.current_ram
            delta_text = f"{ram_delta:+d}"
            detail_bits = [f"{delta_text} RAM", legality.upper()]
            stack_detail_line = "STACK DELTA  " + "   ".join(detail_bits)
            if projection.root_prediction:
                stack_outcome_line = f"STACK OUTCOME  {projection.root_prediction.upper()}"
        defense_text = player.get_defense_summary().replace("DEFENSE     ", "").lower()
        cache_text = player.get_hardening_summary().lower() if player.adaptive_hardening_active else ""
        bot_text = player.get_support_bot_summary().replace("BOT BAY     ", "").lower()
        item_text = player.get_consumable_summary().lower()
        sto = player.subsystems["STO"]
        lines = [
            f"RAM {player.current_ram}/{ram_max}   REGEN {ram_regen}/turn",
        ]
        if stack_detail_line:
            lines.append(stack_detail_line)
        if stack_outcome_line:
            lines.append(stack_outcome_line)
        lines.extend(
            [
                f"{player.handle} // {player.title}",
                f"SIGNATURE  {player.signature_subsystem}   IP {player.local_ip}",
                (
                    f"OS {player.subsystems['OS'].current_hp:>2}/{player.subsystems['OS'].max_hp:<2}   "
                    f"SEC {player.subsystems['SEC'].current_hp:>2}/{player.subsystems['SEC'].max_hp:<2}"
                ),
                (
                    f"NET {player.subsystems['NET'].current_hp:>2}/{player.subsystems['NET'].max_hp:<2}   "
                    f"MEM {player.subsystems['MEM'].current_hp:>2}/{player.subsystems['MEM'].max_hp:<2}   "
                    f"STO {sto.current_hp:>2}/{sto.max_hp:<2}"
                ),
                f"def {defense_text}",
                f"CACHE {cache_text or ('priming' if player.adaptive_hardening_active else 'offline')}",
                f"bots {bot_text}",
                f"items {item_text}",
            ]
        )
        return self.append_runtime_disturbance("player", "\n".join(lines))

    def build_target_text(self) -> str:
        boot_text = self.get_window_boot_text("target")
        if boot_text is not None:
            return boot_text
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
        lines.append("")
        lines.append("BUSES")
        lines.extend(enemy.get_bus_report_lines())
        held_summary = enemy.get_hold_buffer_summary()
        if held_summary != "none":
            lines.extend(["", f"STAGED      {held_summary}"])
        return self.append_runtime_disturbance("target", "\n".join(lines))

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
        boot_text = self.get_window_boot_text("route")
        if boot_text is not None:
            return boot_text
        if self.is_tutorial_staging_state():
            return route_staging_text()
        return self.append_runtime_disturbance("route", self.build_route_map_text())

    def build_log_text(self) -> str:
        boot_text = self.get_window_boot_text("log")
        if boot_text is not None:
            return boot_text
        if self.is_tutorial_staging_state():
            return log_staging_text()
        return self.append_runtime_disturbance("log", self.backend.build_shell_session_log_text())

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
        focus_depth = world.node_depths.get(focus_index, 1)

        lines = [
            world.subnet_name,
            self.backend.map_status or "mesh idle",
            "",
            "[focus]",
            f" {self.describe_route_node(world, focus_index, focus_node)}",
            f" depth {focus_depth}",
        ]

        active_intel = self.backend.build_node_intel_summary(focus_node)
        if active_intel:
            lines.append(f"  {active_intel}")

        ingress_indices = world.get_inbound_hops(focus_index)
        lines.extend(["", "[ingress]"])
        if focus_index in world.entry_links:
            lines.append(" <- shell uplink // public route hop")
        if not ingress_indices:
            if focus_index not in world.entry_links:
                lines.append(" none")
        else:
            for node_index in ingress_indices:
                node = world.nodes[node_index]
                lines.append(f" <- {self.describe_route_node(world, node_index, node)}")

        outbound_indices = sorted(
            world.get_outbound_hops(focus_index),
            key=lambda idx: (world.node_depths.get(idx, 99), world.nodes[idx].ip_address),
        )
        lines.extend(["", "[egress]"])
        if not outbound_indices:
            lines.append(" none")
        else:
            for node_index in outbound_indices:
                node = world.nodes[node_index]
                lines.append(f" -> {self.describe_route_node(world, node_index, node)}")
                intel = self.route_node_secondary_line(world, focus_index, node_index, node)
                if intel:
                    lines.append(f"    {intel}")

                next_hops = world.get_outbound_hops(node_index)
                if next_hops:
                    preview = ", ".join(self.route_node_short_label(world, linked) for linked in next_hops[:3])
                    lines.append(f"    fanout: {preview}")

        return "\n".join(lines)

    def describe_route_node(self, world, node_index: int, node) -> str:
        status = self.backend.get_node_status_text(node_index, node, self.backend.map_cleared)
        label = self.route_node_label(world, node_index, node)
        depth = world.node_depths.get(node_index, 1)
        if label == node.ip_address:
            return f"{label} [{status}] d{depth}"
        return f"{label} @ {node.ip_address} [{status}] d{depth}"

    def route_node_secondary_line(self, world, focus_index: int, node_index: int, node) -> str | None:
        status = self.backend.get_node_status_text(node_index, node, self.backend.map_cleared)
        if status == "LOCKED":
            return "route sealed"
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
        boot_text = self.get_window_boot_text("databank")
        if boot_text is not None:
            return boot_text
        if self.is_tutorial_staging_state():
            return databank_staging_text()
        if getattr(self.backend, "shop_databank_entries", None):
            return self.backend.build_shell_databank_text()
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
            self.tutorial_warmup_release_sent = False
            self.clear_tutorial_live_boot_sequence()
            self.feed.input_locked = False
            if window.isVisible():
                window.hide()
            return

        if not self.tutorial_boot_started:
            self.start_tutorial_boot_sequence()

        if (
            self.is_tutorial_warmup_gate_active()
            and self.tutorial_warmup_requested
            and not self.tutorial_warmup_release_sent
            and bool(self.backend.active_prompt)
        ):
            self.tutorial_warmup_release_sent = True
            self.backend.input_queue.put("")

        if self.tutorial_warmup_gate_pending and self.backend.current_enemy:
            self.tutorial_warmup_gate_pending = False
            self.start_tutorial_live_boot_sequence()

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
