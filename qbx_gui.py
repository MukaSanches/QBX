from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QStyle,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qbx import __version__
from qbx.api import inspect, pack, repair, unpack, verify
from qbx.archive_ops import add_sources, delete_entries, set_comment
from qbx.bridge import create_archive as bridge_create_archive, output_capabilities

APP_NAME = "QBX"
CONFIG_PATH = Path.home() / ".qbx_gui.json"
ROLE_PATH = int(Qt.ItemDataRole.UserRole)
ROLE_KIND = ROLE_PATH + 1


def human_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{int(amount):,} B".replace(",", ".") if unit == "B" else f"{amount:.2f} {unit}"
        amount /= 1024
    return str(value)


def open_with_system(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def self_test() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="qbx-gui-selftest-") as td:
            root = Path(td)
            src = root / "input"
            src.mkdir()
            payload = b"QBX 3.1 GUI SELF TEST\n" * 1400
            (src / "hello.txt").write_bytes(payload)
            (src / "copy.txt").write_bytes(payload)
            archive = root / "selftest.qbx"
            restored = root / "restored"
            made = pack(src, archive, profile="resilient", repair_budget_pct=8.0)
            checked = verify(archive)
            unpack(archive, restored)
            return 0 if (
                made.get("format_version") == 3
                and checked.get("ok") is True
                and (restored / "hello.txt").read_bytes() == payload
            ) else 2
    except Exception:
        traceback.print_exc()
        return 1


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self):
        try:
            value = self.fn()
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        else:
            self.signals.done.emit(value)


def icon_for(kind: str, size: int = 44) -> QIcon:
    """Original QBX vector-like toolbar icons drawn at runtime."""
    colors = {
        "add": "#f0b429",
        "extract": "#5ab0ff",
        "test": "#ef6c73",
        "view": "#76d275",
        "delete": "#8b96a5",
        "find": "#5e83ff",
        "wizard": "#b46cff",
        "info": "#53a7ff",
        "repair": "#65d44f",
        "comment": "#a8b3c2",
        "new": "#36c9a2",
        "open": "#5ab0ff",
        "up": "#c7d2e0",
        "folder": "#f0b429",
        "file": "#8aa7c8",
        "archive": "#4bc7ff",
    }
    glyphs = {
        "add": "+",
        "extract": "↓",
        "test": "✓",
        "view": "▤",
        "delete": "×",
        "find": "⌕",
        "wizard": "✦",
        "info": "i",
        "repair": "↻",
        "comment": "≡",
        "new": "+",
        "open": "▣",
        "up": "↑",
        "folder": "■",
        "file": "□",
        "archive": "Q",
    }
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(colors.get(kind, "#5ab0ff"))
    p.setPen(QPen(color.lighter(140), max(1, size // 22)))
    p.setBrush(color.darker(135))
    margin = max(3, size // 10)
    p.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, size // 7, size // 7)
    p.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI Symbol", max(10, int(size * 0.42)), QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, glyphs.get(kind, "?"))
    p.end()
    return QIcon(pix)


def app_icon() -> QIcon:
    return icon_for("archive", 64)


DARK_STYLESHEET = """
QMainWindow, QWidget {
    background: #202020;
    color: #e9e9e9;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMenuBar {
    background: #202020;
    color: #f3f3f3;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 10px;
    background: transparent;
}
QMenuBar::item:selected {
    background: #343434;
}
QMenu {
    background: #252525;
    color: #f3f3f3;
    border: 1px solid #555;
}
QMenu::item {
    padding: 7px 30px 7px 24px;
}
QMenu::item:selected {
    background: #0b5ca8;
}
QToolBar {
    background: #242424;
    border: 0;
    border-bottom: 1px solid #555;
    spacing: 3px;
    padding: 4px 6px;
}
QToolButton {
    background: transparent;
    color: #efefef;
    border: 0;
    padding: 3px 8px;
    min-width: 58px;
}
QToolButton:hover {
    background: #353535;
    border-radius: 4px;
}
QLineEdit, QComboBox {
    background: #292929;
    color: #f0f0f0;
    border: 1px solid #575757;
    padding: 4px 6px;
}
QPushButton {
    background: #303030;
    color: #eeeeee;
    border: 1px solid #5d5d5d;
    padding: 5px 12px;
}
QPushButton:hover {
    background: #3b3b3b;
}
QTreeWidget {
    background: #1f1f1f;
    alternate-background-color: #232323;
    color: #eaeaea;
    border: 1px solid #555;
    outline: 0;
}
QTreeWidget::item {
    height: 25px;
    padding-left: 2px;
}
QTreeWidget::item:selected {
    background: #0878d1;
    color: white;
}
QHeaderView::section {
    background: #262626;
    color: #efefef;
    border: 0;
    border-right: 1px solid #3a3a3a;
    border-bottom: 1px solid #4a4a4a;
    padding: 5px 7px;
    font-weight: 600;
}
QStatusBar {
    background: #242424;
    color: #e8e8e8;
    border-top: 1px solid #555;
}
QProgressBar {
    background: #191919;
    border: 1px solid #555;
    height: 12px;
}
QProgressBar::chunk {
    background: #0878d1;
}
"""



class CreateArchiveDialog(QDialog):
    """Visual creator for QBX and standard archive formats."""

    def __init__(
        self,
        parent: QWidget,
        initial_sources: list[Path],
        base_dir: Path,
        default_repair_budget: float,
    ):
        super().__init__(parent)
        self.setWindowTitle("Criar arquivo")
        self.setWindowIcon(app_icon())
        self.resize(760, 700)
        self.base_dir = base_dir
        self.sources: list[Path] = []
        self.capabilities = output_capabilities()
        self._build_ui(default_repair_budget)
        for path in initial_sources:
            self.add_source(path)
        self._refresh_default_output(force=True)

    def _build_ui(self, default_repair_budget: float) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(
            "<h2>Criar / otimizar arquivo</h2>"
            "<p>Escolha o formato final. <b>QBX</b> usa toda a tecnologia do projeto. "
            "ZIP, 7z e RAR permanecem formatos padrão para continuarem compatíveis com outros programas.</p>"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        layout.addWidget(QLabel("<b>1. Arquivos, pastas ou arquivos compactados de entrada</b>"))

        self.source_list = QListWidget()
        self.source_list.setMinimumHeight(120)
        layout.addWidget(self.source_list)

        source_buttons = QHBoxLayout()
        add_files = QPushButton("Adicionar arquivos")
        add_folder = QPushButton("Adicionar pasta")
        remove = QPushButton("Remover selecionado")
        add_files.clicked.connect(self._choose_files)
        add_folder.clicked.connect(self._choose_folder)
        remove.clicked.connect(self._remove_selected)
        source_buttons.addWidget(add_files)
        source_buttons.addWidget(add_folder)
        source_buttons.addWidget(remove)
        source_buttons.addStretch(1)
        layout.addLayout(source_buttons)

        form = QFormLayout()

        self.format_combo = QComboBox()
        for fmt in ("qbx", "7z", "zip", "rar"):
            cap = self.capabilities[fmt]
            self.format_combo.addItem(cap["label"], fmt)
            if not cap["available"]:
                model_item = self.format_combo.model().item(self.format_combo.count() - 1)
                if model_item is not None:
                    model_item.setEnabled(False)
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        form.addRow("2. Formato de saída:", self.format_combo)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_edit = QLineEdit()
        browse_output = QPushButton("...")
        browse_output.setFixedWidth(42)
        browse_output.clicked.connect(self._choose_output)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(browse_output)
        form.addRow("3. Arquivo de saída:", output_row)

        self.optimize_checkbox = QCheckBox(
            "Otimizar arquivos compactados de entrada (QBX/ZIP/7z/RAR)"
        )
        self.optimize_checkbox.setChecked(True)
        self.optimize_checkbox.setToolTip(
            "Em vez de recomprimir o arquivo .zip/.7z/.rar pronto, o QBX abre o contêiner "
            "temporariamente e trabalha sobre os arquivos lógicos internos."
        )
        form.addRow("Pré-processamento:", self.optimize_checkbox)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Resiliente V3 — AGRP + ARK (recomendado)", "resilient")
        self.profile_combo.addItem("Adaptativo V2 — AGRP", "adaptive")
        self.profile_combo.addItem("Menor tamanho", "smallest")
        self.profile_combo.addItem("Equilibrado", "balanced")
        self.profile_combo.addItem("Rápido", "fast")
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        form.addRow("Estratégia QBX:", self.profile_combo)

        self.size_goal = QDoubleSpinBox()
        self.size_goal.setRange(0.0, 1024 * 1024.0)
        self.size_goal.setDecimals(2)
        self.size_goal.setSuffix(" MB")
        self.size_goal.setSpecialValueText("Sem limite")
        self.size_goal.setToolTip("Meta opcional de tamanho para o planejador global AGRP.")
        form.addRow("Meta de tamanho:", self.size_goal)

        self.decode_goal = QDoubleSpinBox()
        self.decode_goal.setRange(0.0, 60_000.0)
        self.decode_goal.setDecimals(1)
        self.decode_goal.setSuffix(" ms")
        self.decode_goal.setSpecialValueText("Sem limite")
        self.decode_goal.setToolTip("Meta opcional de custo estimado de decodificação para o AGRP.")
        form.addRow("Meta de decodificação:", self.decode_goal)

        self.repair_budget = QDoubleSpinBox()
        self.repair_budget.setRange(0.0, 100.0)
        self.repair_budget.setDecimals(2)
        self.repair_budget.setSuffix(" %")
        self.repair_budget.setValue(default_repair_budget)
        self.repair_budget.setToolTip(
            "Percentual máximo do payload primário reservado para relações reversíveis ARK."
        )
        form.addRow("Orçamento ARK:", self.repair_budget)

        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(70)
        self.comment_edit.setPlaceholderText("Comentário opcional do manifesto QBX...")
        form.addRow("Comentário QBX:", self.comment_edit)

        layout.addLayout(form)

        self.theory = QLabel()
        self.theory.setWordWrap(True)
        self.theory.setTextFormat(Qt.TextFormat.RichText)
        self.theory.setStyleSheet(
            "QLabel { background:#182635; border:1px solid #31546f; "
            "border-radius:6px; padding:10px; color:#dfefff; }"
        )
        layout.addWidget(self.theory)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.create_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.create_button.setText("Criar arquivo")
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._format_changed()

    def add_source(self, path: Path) -> None:
        path = path.resolve()
        if not path.exists() or path in self.sources:
            return
        self.sources.append(path)
        self.source_list.addItem(str(path))
        self._refresh_default_output(force=not bool(self.output_edit.text().strip()))

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar arquivos",
            str(self.base_dir),
            "Arquivos suportados (*.qbx *.zip *.7z *.rar);;Todos os arquivos (*)",
        )
        for value in files:
            self.add_source(Path(value))

    def _choose_folder(self) -> None:
        value = QFileDialog.getExistingDirectory(self, "Selecionar pasta", str(self.base_dir))
        if value:
            self.add_source(Path(value))

    def _remove_selected(self) -> None:
        rows = sorted(
            {self.source_list.row(item) for item in self.source_list.selectedItems()},
            reverse=True,
        )
        for row in rows:
            self.source_list.takeItem(row)
            del self.sources[row]
        self._refresh_default_output(force=True)

    def _current_format(self) -> str:
        return str(self.format_combo.currentData() or "qbx")

    def _base_output_stem(self) -> str:
        if len(self.sources) == 1:
            name = self.sources[0].name
            lower = name.lower()
            for suffix in (".qbx", ".zip", ".7z", ".rar"):
                if lower.endswith(suffix):
                    return name[: -len(suffix)] or "arquivo"
            return name
        if len(self.sources) > 1:
            return "arquivo"
        return "novo-arquivo"

    def _refresh_default_output(self, *, force: bool = False) -> None:
        if self.output_edit.text().strip() and not force:
            return
        fmt = self._current_format()
        self.output_edit.setText(str(self.base_dir / f"{self._base_output_stem()}.{fmt}"))

    def _choose_output(self) -> None:
        fmt = self._current_format()
        labels = {
            "qbx": "QBX (*.qbx)",
            "zip": "ZIP (*.zip)",
            "7z": "7-Zip (*.7z)",
            "rar": "RAR (*.rar)",
        }
        value, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar arquivo",
            self.output_edit.text() or str(self.base_dir / f"arquivo.{fmt}"),
            labels[fmt],
        )
        if value:
            if not value.lower().endswith(f".{fmt}"):
                value += f".{fmt}"
            self.output_edit.setText(value)

    def _format_changed(self, *_args) -> None:
        fmt = self._current_format()
        is_qbx = fmt == "qbx"
        for widget in (
            self.profile_combo,
            self.size_goal,
            self.decode_goal,
            self.repair_budget,
            self.comment_edit,
        ):
            widget.setEnabled(is_qbx)

        self._refresh_default_output(force=True)
        self._profile_changed()

        if fmt == "qbx":
            self.theory.setText(
                "<b>QBX 3.2 — tecnologia completa:</b><br>"
                "1) arquivos compactados de entrada podem ser abertos antes da recompressão;<br>"
                "2) CDC cria blocos pelo conteúdo;<br>"
                "3) SHA-256 + deduplicação global removem repetição entre arquivos;<br>"
                "4) RAW, Zstandard, Deflate e LZMA são medidos e podados por Pareto;<br>"
                "5) AGRP escolhe o plano global;<br>"
                "6) ARK seleciona relações reversíveis para recuperação;<br>"
                "7) reconstruções só são aceitas se o SHA-256 original conferir."
            )
        elif fmt == "rar":
            available = self.capabilities["rar"]["available"]
            self.theory.setText(
                "<b>RAR5 padrão:</b> o QBX pode primeiro abrir ZIP/7z/RAR/QBX de entrada "
                "para evitar simplesmente recomprimir bytes já compactados e então pedir ao "
                "RAR/WinRAR instalado para criar um RAR5 em compressão alta. "
                "<b>AGRP e ARK não são gravados dentro do RAR padrão</b>, porque isso quebraria "
                "a compatibilidade com o formato RAR."
                + ("" if available else "<br><b>RAR/WinRAR não foi detectado neste computador.</b>")
            )
        elif fmt == "7z":
            self.theory.setText(
                "<b>7z padrão:</b> o bridge pode descompactar contêineres de entrada e criar "
                "um novo 7z/LZMA2 sobre os arquivos reais. Isso evita o caso ZIP-dentro-de-7z. "
                "O resultado continua sendo um 7z convencional; ARK permanece exclusivo do QBX."
            )
        else:
            self.theory.setText(
                "<b>ZIP padrão:</b> o bridge pode descompactar contêineres de entrada e criar "
                "ZIP/Deflate sobre os arquivos reais. O resultado mantém ampla compatibilidade. "
                "O mecanismo ARK não é embutido no ZIP padrão."
            )

    def _profile_changed(self, *_args) -> None:
        if self._current_format() != "qbx":
            return
        resilient = self.profile_combo.currentData() == "resilient"
        self.repair_budget.setEnabled(resilient)

    def _accept_checked(self) -> None:
        if not self.sources:
            QMessageBox.warning(self, APP_NAME, "Adicione pelo menos um arquivo ou pasta.")
            return

        fmt = self._current_format()
        if not self.capabilities[fmt]["available"]:
            QMessageBox.warning(
                self,
                APP_NAME,
                "Esse formato não está disponível neste computador. "
                "Para gerar RAR, instale WinRAR/RAR ou configure QBX_RAR_EXE.",
            )
            return

        output = self.output_edit.text().strip()
        if not output:
            QMessageBox.warning(self, APP_NAME, "Escolha o arquivo de saída.")
            return

        out = Path(output)
        if out.suffix.lower() != f".{fmt}":
            out = out.with_suffix(f".{fmt}")
            self.output_edit.setText(str(out))

        if any(src.resolve() == out.resolve() for src in self.sources):
            QMessageBox.warning(self, APP_NAME, "O arquivo de saída não pode ser uma das fontes.")
            return
        self.accept()

    def options(self) -> dict:
        max_size = float(self.size_goal.value())
        max_decode = float(self.decode_goal.value())
        return {
            "sources": list(self.sources),
            "output": Path(self.output_edit.text()),
            "output_format": self._current_format(),
            "optimize_source_archives": self.optimize_checkbox.isChecked(),
            "profile": str(self.profile_combo.currentData()),
            "max_size_mb": max_size if max_size > 0 else None,
            "max_decode_ms": max_decode if max_decode > 0 else None,
            "repair_budget_pct": float(self.repair_budget.value()),
            "comment": self.comment_edit.toPlainText(),
        }


class QBXWindow(QMainWindow):
    def __init__(self, initial_archive: str | None = None):
        super().__init__()
        self.setWindowTitle(f"QBX {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1280, 760)
        self.setMinimumSize(900, 560)
        self.setAcceptDrops(True)

        self.archive_path: Path | None = None
        self.manifest: dict | None = None
        self.archive_dir = PurePosixPath(".")
        self.fs_dir = Path.home()
        self.mode = "filesystem"
        self._temp_views: list[str] = []
        self._busy = False
        self.thread_pool = QThreadPool.globalInstance()
        self.config_data = self._load_config()
        self.repair_budget_pct = float(self.config_data.get("repair_budget_pct", 5.0))

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self._build_status()
        self.setStyleSheet(DARK_STYLESHEET)

        if initial_archive:
            self.open_archive(Path(initial_archive))
        else:
            self.refresh_view()

    # ---------- config ----------

    def _load_config(self) -> dict:
        try:
            obj = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _save_config(self) -> None:
        try:
            CONFIG_PATH.write_text(
                json.dumps(self.config_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ---------- UI shell ----------

    def _action(self, text: str, icon: str, slot, shortcut: str | None = None) -> QAction:
        a = QAction(icon_for(icon), text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    def _build_actions(self) -> None:
        self.act_new = self._action("Criar Arquivo", "new", self.create_new_archive, "Ctrl+N")
        self.act_open = self._action("Abrir arquivo...", "open", self.choose_archive, "Ctrl+O")
        self.act_add = self._action("Adicionar", "add", self.add_clicked, "Alt+A")
        self.act_extract = self._action("Extrair Para", "extract", self.extract_clicked, "Alt+E")
        self.act_test = self._action("Testar", "test", self.verify_clicked, "Alt+T")
        self.act_view = self._action("Visualizar", "view", self.view_clicked, "F3")
        self.act_delete = self._action("Excluir", "delete", self.delete_clicked, "Delete")
        self.act_find = self._action("Localizar", "find", self.find_clicked, "F4")
        self.act_wizard = self._action("Assistente", "wizard", self.create_new_archive)
        self.act_info = self._action("Informações", "info", self.show_info, "Alt+I")
        self.act_repair = self._action("Reparar", "repair", self.repair_archive)
        self.act_comment = self._action("Comentários", "comment", self.edit_comment)
        self.act_close = QAction("Fechar arquivo", self)
        self.act_close.triggered.connect(self.close_archive)
        self.act_exit = QAction("Sair", self)
        self.act_exit.triggered.connect(self.close)
        self.act_up = self._action("Um nível acima", "up", self.go_up, "Backspace")

    def _build_menus(self) -> None:
        bar = self.menuBar()

        m_file = bar.addMenu("Arquivo")
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)
        m_file.addSeparator()
        m_file.addAction(self.act_close)
        m_file.addSeparator()
        m_file.addAction(self.act_exit)

        m_commands = bar.addMenu("Comandos")
        for action in (
            self.act_new,
            self.act_add,
            self.act_extract,
            self.act_test,
            self.act_view,
            self.act_delete,
            self.act_find,
            self.act_repair,
            self.act_comment,
        ):
            m_commands.addAction(action)

        m_tools = bar.addMenu("Ferramentas")
        m_tools.addAction(self.act_wizard)
        m_tools.addAction(self.act_info)
        tech_action = QAction("Tecnologia QBX: AGRP + ARK", self)
        tech_action.triggered.connect(self.show_technology)
        m_tools.addAction(tech_action)
        hash_action = QAction("Copiar SHA-256 do arquivo QBX", self)
        hash_action.triggered.connect(self.copy_archive_hash)
        m_tools.addAction(hash_action)

        self.menu_favorites = bar.addMenu("Favoritos")
        self._rebuild_favorites_menu()

        m_options = bar.addMenu("Opções")
        budget = QAction("Orçamento ARK...", self)
        budget.triggered.connect(self.configure_repair_budget)
        m_options.addAction(budget)

        m_help = bar.addMenu("Ajuda")
        about = QAction("Sobre o QBX", self)
        about.triggered.connect(self.show_about)
        m_help.addAction(about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principal", self)
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(42, 42))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        for action in (
            self.act_add,
            self.act_extract,
            self.act_test,
            self.act_view,
            self.act_delete,
            self.act_find,
            self.act_wizard,
            self.act_info,
            self.act_repair,
            self.act_comment,
        ):
            tb.addAction(action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

    def _build_central(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        row = QWidget(root)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        nav = QWidget(row)
        from PySide6.QtWidgets import QHBoxLayout
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        up = QPushButton("↑")
        up.setFixedWidth(42)
        up.setToolTip("Um nível acima")
        up.clicked.connect(self.go_up)

        self.address = QLineEdit()
        self.address.setReadOnly(True)

        nav_layout.addWidget(up)
        nav_layout.addWidget(self.address, 1)

        self.info_line = QLineEdit()
        self.info_line.setReadOnly(True)

        row_layout.addWidget(nav)
        row_layout.addWidget(self.info_line)
        layout.addWidget(row)

        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(False)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(
            ["Nome", "Tamanho", "Compactado", "Tipo", "Modificado", "SHA-256", "Método"]
        )
        self.tree.setColumnWidth(0, 390)
        self.tree.setColumnWidth(1, 115)
        self.tree.setColumnWidth(2, 115)
        self.tree.setColumnWidth(3, 150)
        self.tree.setColumnWidth(4, 150)
        self.tree.setColumnWidth(5, 150)
        self.tree.setColumnWidth(6, 120)
        self.tree.itemDoubleClicked.connect(self._double_click)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.tree, 1)

        self.setCentralWidget(root)

    def _build_status(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self.status_left = QLabel("Pronto")
        self.status_right = QLabel(f"QBX {__version__}  |  AGRP + ARK")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(150)
        self.progress.hide()
        bar.addWidget(self.status_left, 1)
        bar.addPermanentWidget(self.progress)
        bar.addPermanentWidget(self.status_right)

    # ---------- async ----------

    def _run(self, label: str, fn, done=None) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_left.setText(label)
        self.progress.show()
        for a in (
            self.act_add, self.act_extract, self.act_test, self.act_view,
            self.act_delete, self.act_find, self.act_wizard, self.act_info,
            self.act_repair, self.act_comment
        ):
            a.setEnabled(False)

        worker = Worker(fn)
        worker.signals.done.connect(lambda value: self._task_done(value, done))
        worker.signals.error.connect(self._task_error)
        self.thread_pool.start(worker)

    def _task_done(self, value, done) -> None:
        self._busy = False
        self.progress.hide()
        for a in (
            self.act_add, self.act_extract, self.act_test, self.act_view,
            self.act_delete, self.act_find, self.act_wizard, self.act_info,
            self.act_repair, self.act_comment
        ):
            a.setEnabled(True)
        self.status_left.setText("Pronto")
        if done:
            done(value)

    def _task_error(self, details: str) -> None:
        self._task_done(None, None)
        short = details.strip().splitlines()[-1] if details.strip() else "Erro desconhecido"
        QMessageBox.critical(self, APP_NAME, f"{short}\n\nDetalhes foram registrados no traceback da execução.")
        print(details, file=sys.stderr)

    # ---------- file-system / archive navigation ----------

    def refresh_view(self) -> None:
        if self.mode == "archive" and self.manifest is not None:
            self._populate_archive()
        else:
            self._populate_filesystem()

    def _populate_filesystem(self) -> None:
        self.mode = "filesystem"
        self.tree.clear()
        self.address.setText(str(self.fs_dir))
        self.info_line.setText(f"{self.fs_dir}  —  modo gerenciador de arquivos")
        self.setWindowTitle(f"QBX {__version__}")

        if self.fs_dir.parent != self.fs_dir:
            item = QTreeWidgetItem(["..", "", "", "Pasta", "", "", ""])
            item.setIcon(0, icon_for("up", 22))
            item.setData(0, ROLE_PATH, str(self.fs_dir.parent))
            item.setData(0, ROLE_KIND, "fs-dir")
            self.tree.addTopLevelItem(item)

        try:
            entries = sorted(
                self.fs_dir.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.casefold()),
            )
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            entries = []

        for p in entries:
            try:
                st = p.stat()
            except OSError:
                continue
            is_dir = p.is_dir()
            size = "" if is_dir else human_bytes(st.st_size)
            kind = "Pasta de arquivos" if is_dir else (p.suffix.upper().lstrip(".") + " File" if p.suffix else "Arquivo")
            modified = __import__("time").strftime("%d/%m/%Y %H:%M", __import__("time").localtime(st.st_mtime))
            item = QTreeWidgetItem([p.name, size, "", kind, modified, "", ""])
            item.setIcon(0, icon_for("folder" if is_dir else ("archive" if p.suffix.lower() == ".qbx" else "file"), 22))
            item.setData(0, ROLE_PATH, str(p))
            item.setData(0, ROLE_KIND, "fs-dir" if is_dir else "fs-file")
            self.tree.addTopLevelItem(item)

        self.status_left.setText(f"{len(entries)} item(ns)")

    def _populate_archive(self) -> None:
        assert self.manifest is not None and self.archive_path is not None
        self.tree.clear()
        prefix = "" if str(self.archive_dir) == "." else self.archive_dir.as_posix().rstrip("/") + "/"
        display_prefix = prefix.replace("/", "\\")
        self.address.setText(f"{self.archive_path}  \\  {display_prefix}")
        stats = self.manifest.get("statistics", {})
        original = stats.get("input_bytes", 0)
        self.info_line.setText(
            f"{self.archive_path.name} — Arquivo QBX V{self.manifest.get('version', '?')}, "
            f"tamanho original {human_bytes(original)}, "
            f"{stats.get('repair_edges', 0)} relação(ões) ARK"
        )
        self.setWindowTitle(f"{self.archive_path.name} - QBX {__version__}")

        if str(self.archive_dir) != ".":
            item = QTreeWidgetItem(["..", "", "", "Pasta", "", "", ""])
            item.setIcon(0, icon_for("up", 22))
            item.setData(0, ROLE_PATH, str(self.archive_dir.parent))
            item.setData(0, ROLE_KIND, "archive-dir")
            self.tree.addTopLevelItem(item)

        child_dirs: set[str] = set()
        for d in self.manifest.get("directories", []):
            if d.startswith(prefix):
                rest = d[len(prefix):]
                if rest and "/" not in rest:
                    child_dirs.add(rest)
        for e in self.manifest.get("files", []):
            path = e["path"]
            if path.startswith(prefix):
                rest = path[len(prefix):]
                if "/" in rest:
                    child_dirs.add(rest.split("/", 1)[0])

        for name in sorted(child_dirs, key=str.casefold):
            full = prefix + name
            item = QTreeWidgetItem([name, "", "", "Pasta de arquivos", "", "", ""])
            item.setIcon(0, icon_for("folder", 22))
            item.setData(0, ROLE_PATH, full)
            item.setData(0, ROLE_KIND, "archive-dir")
            self.tree.addTopLevelItem(item)

        visible_files = []
        for e in self.manifest.get("files", []):
            path = e["path"]
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            if "/" in rest:
                continue
            visible_files.append((rest, e))

        for name, e in sorted(visible_files, key=lambda x: x[0].casefold()):
            modified = ""
            if isinstance(e.get("mtime_ns"), int):
                try:
                    import time
                    modified = time.strftime("%d/%m/%Y %H:%M", time.localtime(e["mtime_ns"] / 1e9))
                except Exception:
                    pass
            method = self.manifest.get("compression_profile", "QBX")
            item = QTreeWidgetItem([
                name,
                human_bytes(e.get("size")),
                "—",
                Path(name).suffix.upper().lstrip(".") or "Arquivo",
                modified,
                e.get("sha256", "")[:16].upper(),
                method,
            ])
            item.setIcon(0, icon_for("file", 22))
            item.setData(0, ROLE_PATH, e["path"])
            item.setData(0, ROLE_KIND, "archive-file")
            self.tree.addTopLevelItem(item)

        total = len(self.manifest.get("files", []))
        self.status_left.setText(
            f"Total {len(child_dirs)} pasta(s) e {total} arquivo(s), "
            f"{human_bytes(original)}"
        )

    def _double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        kind = item.data(0, ROLE_KIND)
        path = item.data(0, ROLE_PATH)
        if not path:
            return
        if kind == "fs-dir":
            self.fs_dir = Path(path)
            self.refresh_view()
        elif kind == "fs-file":
            p = Path(path)
            if p.suffix.lower() == ".qbx":
                self.open_archive(p)
            else:
                open_with_system(p)
        elif kind == "archive-dir":
            self.archive_dir = PurePosixPath(path)
            if str(self.archive_dir) == "":
                self.archive_dir = PurePosixPath(".")
            self.refresh_view()
        elif kind == "archive-file":
            self.view_clicked()

    def go_up(self) -> None:
        if self.mode == "archive":
            if str(self.archive_dir) == ".":
                self.close_archive()
            else:
                parent = self.archive_dir.parent
                self.archive_dir = PurePosixPath(".") if str(parent) in ("", ".") else parent
                self.refresh_view()
        else:
            if self.fs_dir.parent != self.fs_dir:
                self.fs_dir = self.fs_dir.parent
                self.refresh_view()

    def _selected(self) -> list[tuple[str, str]]:
        result = []
        for item in self.tree.selectedItems():
            path = item.data(0, ROLE_PATH)
            kind = item.data(0, ROLE_KIND)
            if path and kind:
                result.append((str(path), str(kind)))
        return result

    def _selection_changed(self) -> None:
        selected = self._selected()
        if not selected:
            return
        if self.mode == "filesystem":
            total = 0
            count = 0
            for p, kind in selected:
                if kind == "fs-file":
                    try:
                        total += Path(p).stat().st_size
                        count += 1
                    except OSError:
                        pass
            if count:
                self.status_left.setText(f"Selecionado {count} arquivo(s), {human_bytes(total)}")
        else:
            self.status_left.setText(f"Selecionado {len(selected)} item(ns)")

    # ---------- archive lifecycle ----------

    def choose_archive(self) -> None:
        value, _ = QFileDialog.getOpenFileName(self, "Abrir arquivo QBX", str(self.fs_dir), "QBX (*.qbx);;Todos os arquivos (*)")
        if value:
            self.open_archive(Path(value))

    def open_archive(self, path: Path) -> None:
        path = path.resolve()

        def done(manifest: dict) -> None:
            self.archive_path = path
            self.manifest = manifest
            self.archive_dir = PurePosixPath(".")
            self.mode = "archive"
            self._remember_recent(path)
            self.refresh_view()

        self._run(f"Abrindo {path.name}...", lambda: inspect(path), done)

    def close_archive(self) -> None:
        if self.archive_path:
            self.fs_dir = self.archive_path.parent
        self.archive_path = None
        self.manifest = None
        self.archive_dir = PurePosixPath(".")
        self.mode = "filesystem"
        self.refresh_view()

    def _stage_and_pack(self, options: dict) -> dict:
        return bridge_create_archive(
            options["sources"],
            options["output"],
            output_format=options["output_format"],
            optimize_source_archives=options["optimize_source_archives"],
            qbx_profile=options["profile"],
            max_size_mb=options["max_size_mb"],
            max_decode_ms=options["max_decode_ms"],
            repair_budget_pct=options["repair_budget_pct"],
            comment=options["comment"],
        )

    def create_new_archive(self) -> None:
        selected = [
            Path(p)
            for p, kind in self._selected()
            if self.mode == "filesystem"
            and kind in {"fs-file", "fs-dir"}
            and Path(p).name != ".."
        ]

        dialog = CreateArchiveDialog(
            self,
            initial_sources=selected,
            base_dir=self.fs_dir,
            default_repair_budget=self.repair_budget_pct,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        options = dialog.options()
        self.repair_budget_pct = float(options["repair_budget_pct"])
        self.config_data["repair_budget_pct"] = self.repair_budget_pct
        self._save_config()
        out: Path = options["output"]

        if options["output_format"] == "qbx":
            profile_label = (
                "AGRP + ARK"
                if options["profile"] == "resilient"
                else options["profile"].upper()
            )
        else:
            profile_label = "Universal Bridge"
        self._run(
            f"Criando {options['output_format'].upper()} com {profile_label}...",
            lambda: self._stage_and_pack(options),
            lambda result: self._archive_created(out, result),
        )

    def _archive_created(self, out: Path, result: dict) -> None:
        fmt = result.get("output_format", out.suffix.lstrip(".")).upper()
        optimized = result.get("optimized_source_archives", 0)
        details = [
            "Arquivo criado com sucesso.",
            "",
            f"Saída: {Path(result.get('output', out)).name}",
            f"Formato: {fmt}",
            f"Tamanho: {human_bytes(result.get('archive', 0))}",
            f"Contêineres de entrada otimizados: {optimized}",
        ]
        if result.get("output_format") == "qbx":
            details.extend(
                [
                    f"Perfil: {result.get('profile', '')}",
                    f"Planner: {result.get('planner', 'legacy')}",
                    f"Relações ARK: {result.get('repair_edges', 0)}",
                    f"SHA-256: {result.get('archive_sha256', '')[:24]}...",
                ]
            )
        else:
            details.append(f"Tecnologia do formato: {result.get('format_technology', '')}")
            details.append("AGRP/ARK embutido: não — saída padrão compatível")

        QMessageBox.information(self, "Arquivo criado", "\n".join(details))

        if result.get("output_format") == "qbx":
            self.open_archive(Path(result.get("output", out)))
        else:
            self.fs_dir = Path(result.get("output", out)).parent
            self.refresh_view()


    # ---------- toolbar commands ----------

    def add_clicked(self) -> None:
        if self.mode == "filesystem":
            self.create_new_archive()
            return
        if not self.archive_path:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Adicionar arquivos", str(self.fs_dir), "Todos os arquivos (*)")
        sources = [Path(p) for p in files]
        if not sources:
            folder = QFileDialog.getExistingDirectory(self, "Adicionar pasta", str(self.fs_dir))
            if folder:
                sources = [Path(folder)]
        if not sources:
            return
        self._run(
            "Adicionando e reconstruindo o arquivo...",
            lambda: add_sources(
                self.archive_path,
                [str(x) for x in sources],
                overwrite_entries=True,
                repair_budget_pct=self.repair_budget_pct,
            ),
            lambda _r: self.open_archive(self.archive_path),
        )

    def extract_clicked(self) -> None:
        archive = self.archive_path
        if self.mode == "filesystem":
            selected = [Path(p) for p, kind in self._selected() if kind == "fs-file" and Path(p).suffix.lower() == ".qbx"]
            if len(selected) != 1:
                QMessageBox.information(self, APP_NAME, "Selecione um arquivo .qbx para extrair.")
                return
            archive = selected[0]
        if archive is None:
            return
        dest = QFileDialog.getExistingDirectory(self, "Extrair para", str(archive.parent))
        if not dest:
            return

        def done(result: dict) -> None:
            QMessageBox.information(
                self,
                APP_NAME,
                f"Extração concluída.\n\n"
                f"Arquivos: {result.get('files', 0)}\n"
                f"Dados: {human_bytes(result.get('bytes', 0))}\n"
                f"Blocos recuperados: {result.get('recovered_blocks', 0)}",
            )

        self._run("Extraindo e verificando...", lambda: unpack(archive, dest), done)

    def verify_clicked(self) -> None:
        archive = self.archive_path
        if self.mode == "filesystem":
            selected = [Path(p) for p, kind in self._selected() if kind == "fs-file" and Path(p).suffix.lower() == ".qbx"]
            if len(selected) == 1:
                archive = selected[0]
        if archive is None:
            QMessageBox.information(self, APP_NAME, "Abra ou selecione um arquivo QBX.")
            return

        def done(result: dict) -> None:
            state = "SAUDÁVEL"
            if result.get("degraded"):
                state = "DEGRADADO, MAS RECUPERÁVEL"
            QMessageBox.information(
                self,
                "Teste do arquivo",
                f"Estado: {state}\n\n"
                f"Arquivos: {result.get('files', 0)}\n"
                f"Blocos: {result.get('blocks', 0)}\n"
                f"Blocos recuperados: {result.get('recovered_blocks', 0)}\n"
                f"Registros danificados: {result.get('damaged_records', 0)}",
            )

        self._run("Testando integridade e caminhos ARK...", lambda: verify(archive), done)

    def view_clicked(self) -> None:
        selected = self._selected()
        if len(selected) != 1:
            QMessageBox.information(self, APP_NAME, "Selecione exatamente um arquivo.")
            return
        path, kind = selected[0]
        if kind == "fs-file":
            open_with_system(Path(path))
            return
        if kind != "archive-file" or not self.archive_path:
            return

        rel = path

        def work():
            td = tempfile.mkdtemp(prefix="qbx-view-")
            self._temp_views.append(td)
            unpack(self.archive_path, td)
            return Path(td).joinpath(*PurePosixPath(rel).parts)

        self._run("Preparando visualização...", work, open_with_system)

    def delete_clicked(self) -> None:
        if self.mode != "archive" or not self.archive_path:
            QMessageBox.information(self, APP_NAME, "A exclusão direta do sistema de arquivos não é realizada pelo QBX.")
            return
        paths = [p for p, kind in self._selected() if kind in {"archive-file", "archive-dir"} and p != ".."]
        if not paths:
            return
        if QMessageBox.question(self, APP_NAME, f"Excluir {len(paths)} item(ns) do arquivo?") != QMessageBox.StandardButton.Yes:
            return
        self._run(
            "Excluindo e reconstruindo o arquivo...",
            lambda: delete_entries(self.archive_path, paths, repair_budget_pct=self.repair_budget_pct),
            lambda _r: self.open_archive(self.archive_path),
        )

    def find_clicked(self) -> None:
        term, ok = QInputDialog.getText(self, "Localizar", "Nome ou caminho contém:")
        if not ok or not term:
            return
        needle = term.casefold()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if needle in item.text(0).casefold():
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return
        if self.mode == "archive" and self.manifest:
            match = next((e for e in self.manifest.get("files", []) if needle in e["path"].casefold()), None)
            if match:
                parent = PurePosixPath(match["path"]).parent
                self.archive_dir = PurePosixPath(".") if str(parent) == "." else parent
                self.refresh_view()
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    if item.text(0) == PurePosixPath(match["path"]).name:
                        self.tree.setCurrentItem(item)
                        self.tree.scrollToItem(item)
                        return
        QMessageBox.information(self, APP_NAME, "Nenhum resultado encontrado.")

    def repair_archive(self) -> None:
        if not self.archive_path:
            QMessageBox.information(self, APP_NAME, "Abra um arquivo QBX primeiro.")
            return
        output, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar arquivo reparado",
            str(self.archive_path.with_name(self.archive_path.stem + "-reparado.qbx")),
            "QBX (*.qbx)",
        )
        if not output:
            return
        out = Path(output)

        def done(result: dict) -> None:
            QMessageBox.information(
                self,
                APP_NAME,
                f"Reparo concluído.\n\nBlocos recuperados: {result.get('recovered_blocks', 0)}",
            )
            self.open_archive(out)

        self._run(
            "Reconstruindo arquivo limpo com ARK...",
            lambda: repair(self.archive_path, out, repair_budget_pct=self.repair_budget_pct),
            done,
        )

    def edit_comment(self) -> None:
        if not self.archive_path or not self.manifest:
            return
        value, ok = QInputDialog.getMultiLineText(
            self,
            "Comentários",
            "Comentário do arquivo:",
            str(self.manifest.get("comment", "")),
        )
        if not ok:
            return
        self._run(
            "Atualizando comentário...",
            lambda: set_comment(self.archive_path, value, repair_budget_pct=self.repair_budget_pct),
            lambda _r: self.open_archive(self.archive_path),
        )

    def show_info(self) -> None:
        if self.mode == "filesystem":
            selected = self._selected()
            if len(selected) == 1:
                p = Path(selected[0][0])
                try:
                    st = p.stat()
                    QMessageBox.information(
                        self,
                        "Informações",
                        f"Nome: {p.name}\nCaminho: {p}\nTipo: {'Pasta' if p.is_dir() else 'Arquivo'}\n"
                        f"Tamanho: {human_bytes(st.st_size) if p.is_file() else '—'}",
                    )
                except OSError as exc:
                    QMessageBox.warning(self, APP_NAME, str(exc))
            return
        if not self.archive_path or not self.manifest:
            return
        stats = self.manifest.get("statistics", {})
        planner = self.manifest.get("planner", {})
        QMessageBox.information(
            self,
            "Informações do arquivo QBX",
            f"Arquivo: {self.archive_path.name}\n"
            f"Formato: QBX V{self.manifest.get('version', '?')}\n"
            f"Produto: {self.manifest.get('product_version', __version__)}\n"
            f"Perfil: {self.manifest.get('compression_profile', '')}\n"
            f"Arquivos: {stats.get('file_count', 0)}\n"
            f"Tamanho original: {human_bytes(stats.get('input_bytes', 0))}\n"
            f"Blocos únicos: {stats.get('unique_blocks', 0)}\n"
            f"Relações ARK: {stats.get('repair_edges', 0)}\n"
            f"Planner: {planner.get('name', 'legacy')}\n"
            f"Comentário: {self.manifest.get('comment', '') or '(nenhum)'}",
        )

    def copy_archive_hash(self) -> None:
        if not self.archive_path:
            return

        def work() -> str:
            h = hashlib.sha256()
            with self.archive_path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()

        def done(value: str) -> None:
            QApplication.clipboard().setText(value)
            self.status_left.setText("SHA-256 copiado")

        self._run("Calculando SHA-256...", work, done)

    # ---------- favorites/options/help ----------

    def _remember_recent(self, path: Path) -> None:
        recent = [str(path)] + [x for x in self.config_data.get("recent", []) if x != str(path)]
        self.config_data["recent"] = recent[:12]
        self._save_config()

    def _rebuild_favorites_menu(self) -> None:
        self.menu_favorites.clear()
        add = QAction("Adicionar arquivo atual aos favoritos", self)
        add.triggered.connect(self.add_favorite)
        self.menu_favorites.addAction(add)
        self.menu_favorites.addSeparator()
        favorites = self.config_data.get("favorites", [])
        if not favorites:
            empty = QAction("(nenhum favorito)", self)
            empty.setEnabled(False)
            self.menu_favorites.addAction(empty)
            return
        for value in favorites:
            action = QAction(Path(value).name, self)
            action.triggered.connect(lambda _checked=False, p=value: self.open_archive(Path(p)))
            self.menu_favorites.addAction(action)

    def add_favorite(self) -> None:
        if not self.archive_path:
            return
        favorites = list(self.config_data.get("favorites", []))
        value = str(self.archive_path)
        if value not in favorites:
            favorites.append(value)
            self.config_data["favorites"] = favorites
            self._save_config()
            self._rebuild_favorites_menu()

    def configure_repair_budget(self) -> None:
        value, ok = QInputDialog.getDouble(
            self,
            "Orçamento ARK",
            "Percentual máximo do payload primário reservado para reparo:",
            self.repair_budget_pct,
            0.0,
            100.0,
            2,
        )
        if ok:
            self.repair_budget_pct = float(value)
            self.config_data["repair_budget_pct"] = self.repair_budget_pct
            self._save_config()

    def show_technology(self) -> None:
        QMessageBox.information(
            self,
            "Tecnologia QBX 3.1",
            "QBX 3.1 integra as camadas criadas no projeto:\n\n"
            "• CDC — divide conteúdo em blocos por padrões dos próprios dados.\n"
            "• SHA-256 — dá identidade verificável a cada bloco e arquivo.\n"
            "• Deduplicação global — blocos repetidos são armazenados uma única vez.\n"
            "• Multi-codec — RAW, Zstandard, Deflate e LZMA são medidos por bloco.\n"
            "• Pareto — elimina representações claramente inferiores.\n"
            "• AGRP — escolhe o plano global conforme tamanho e custo de leitura.\n"
            "• ARK — seleciona relações reversíveis entre blocos sob orçamento real de bytes.\n"
            "• Recuperação autenticada — um bloco reconstruído só é aceito se o SHA-256 conferir.\n\n"
            "Na interface, use Criar Arquivo. Para .qbx, escolha Resiliente V3 para o caminho completo. "
            "Para ZIP/7z/RAR, o Bridge Universal pode abrir previamente arquivos compactados de entrada e então "
            "gerar um formato padrão; AGRP e ARK continuam exclusivos do contêiner .qbx para não quebrar compatibilidade."
        )

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "Sobre o QBX",
            f"QBX {__version__}\n\n"
            "Gerenciador de arquivos e formato adaptativo resiliente.\n"
            "AGRP: planejamento global de representações.\n"
            "ARK: relações reversíveis para recuperação de blocos.\n\n"
            "A interface segue o fluxo clássico de gerenciadores de arquivos compactados, "
            "com identidade e ícones próprios do QBX.",
        )

    # ---------- drag/drop ----------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        if len(paths) == 1 and paths[0].suffix.lower() == ".qbx":
            self.open_archive(paths[0])
            event.acceptProposedAction()
            return
        if self.mode == "archive" and self.archive_path:
            self._run(
                "Adicionando itens arrastados...",
                lambda: add_sources(
                    self.archive_path,
                    [str(p) for p in paths],
                    overwrite_entries=True,
                    repair_budget_pct=self.repair_budget_pct,
                ),
                lambda _r: self.open_archive(self.archive_path),
            )
        event.acceptProposedAction()

    def closeEvent(self, event):
        for td in self._temp_views:
            shutil.rmtree(td, ignore_errors=True)
        event.accept()


def ui_smoke_test() -> int:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(["qbx-ui-smoke"])
        window = QBXWindow()
        window.show()
        app.processEvents()
        window.close()
        app.processEvents()
        return 0
    except Exception:
        traceback.print_exc()
        return 1


def _extract_here(archive: str) -> int:
    path = Path(archive)
    unpack(path, path.parent / path.stem, overwrite=False)
    return 0


def _create_from_shell(source: str) -> int:
    path = Path(source)
    pack(path, path.with_name(path.name + ".qbx"), profile="resilient")
    return 0


def main() -> int:
    if "--version" in sys.argv:
        print(f"QBX {__version__}")
        return 0
    if "--self-test" in sys.argv:
        return self_test()
    if "--ui-smoke-test" in sys.argv:
        return ui_smoke_test()
    if "--extract-here" in sys.argv:
        i = sys.argv.index("--extract-here")
        return 2 if i + 1 >= len(sys.argv) else _extract_here(sys.argv[i + 1])
    if "--create" in sys.argv:
        i = sys.argv.index("--create")
        return 2 if i + 1 >= len(sys.argv) else _create_from_shell(sys.argv[i + 1])

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    initial = next((a for a in sys.argv[1:] if not a.startswith("-") and a.lower().endswith(".qbx")), None)
    window = QBXWindow(initial_archive=initial)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
