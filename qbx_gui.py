from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from qbx import __version__
from qbx.api import inspect, pack, repair, unpack, verify
from qbx.archive_ops import add_sources, delete_entries, set_comment

APP_NAME = "QBX"
CONFIG_PATH = Path.home() / ".qbx_gui.json"


def human_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{int(amount)} B" if unit == "B" else f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{value} B"


def self_test() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="qbx-gui-selftest-") as td:
            root = Path(td)
            src = root / "input"
            src.mkdir()
            payload = b"QBX V3 GUI SELF TEST\n" * 1200
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
        return 1


class QBXApp(tk.Tk):
    """Classic Windows archive-manager shell with original QBX branding."""

    def __init__(self, initial_archive: str | None = None):
        super().__init__()
        self.title(f"QBX {__version__}")
        self.geometry("1120x720")
        self.minsize(900, 580)

        self.archive_path: Path | None = None
        self.manifest: dict | None = None
        self.current_dir = PurePosixPath(".")
        self.item_paths: dict[str, str] = {}
        self.status_var = tk.StringVar(value="Pronto")
        self.address_var = tk.StringVar(value="QBX\\")
        self._busy = False
        self._temp_views: list[str] = []
        self.config_data = self._load_config()
        self.repair_budget_pct = float(self.config_data.get("repair_budget_pct", 5.0))

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if initial_archive:
            self.after(150, lambda: self.open_archive(Path(initial_archive)))

    def _load_config(self) -> dict:
        try:
            value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
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

    def _build_ui(self) -> None:
        self.option_add("*Font", "Segoe UI 9")
        self._build_menu()
        self._build_toolbar()

        address = tk.Frame(self, bd=1, relief="sunken", bg="#efefef")
        address.pack(fill="x", padx=3, pady=(2, 0))
        tk.Button(address, text="Up", width=5, command=self.go_up).pack(side="left", padx=2, pady=2)
        tk.Label(address, text="Address", bg="#efefef").pack(side="left", padx=(5, 5))
        ttk.Entry(address, textvariable=self.address_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(0, 4), pady=3
        )

        area = ttk.Frame(self)
        area.pack(fill="both", expand=True, padx=3, pady=3)
        columns = ("name", "size", "blocks", "type", "modified", "hash")
        self.tree = ttk.Treeview(area, columns=columns, show="headings", selectmode="extended")
        specs = {
            "name": ("Name", 380, "w"),
            "size": ("Size", 110, "e"),
            "blocks": ("Blocks", 70, "e"),
            "type": ("Type", 120, "w"),
            "modified": ("Modified", 145, "w"),
            "hash": ("SHA-256", 170, "w"),
        }
        for col, (label, width, anchor) in specs.items():
            self.tree.heading(col, text=label, command=lambda c=col: self._sort_tree(c, False))
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self._double_click)
        self.tree.bind("<Return>", self._double_click)
        self.tree.bind("<BackSpace>", lambda _e: self.go_up())
        scroll = ttk.Scrollbar(area, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        status = tk.Frame(self, bd=1, relief="sunken")
        status.pack(fill="x", side="bottom")
        ttk.Label(status, textvariable=self.status_var, anchor="w").pack(
            side="left", fill="x", expand=True, padx=5, pady=2
        )
        ttk.Label(status, text=f"QBX {__version__} | AGRP + ARK", anchor="e").pack(
            side="right", padx=5
        )

        self.bind_all("<Control-o>", lambda _e: self.choose_archive())
        self.bind_all("<Control-n>", lambda _e: self.create_new_archive())
        self.bind_all("<Control-f>", lambda _e: self.find_entry())

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        self.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New archive...", command=self.create_new_archive, accelerator="Ctrl+N")
        file_menu.add_command(label="Open archive...", command=self.choose_archive, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Close archive", command=self.close_archive)
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        commands = tk.Menu(menu, tearoff=False)
        commands.add_command(label="Add files...", command=lambda: self.add_to_archive(False))
        commands.add_command(label="Add folder...", command=lambda: self.add_to_archive(True))
        commands.add_command(label="Extract to...", command=self.extract_archive)
        commands.add_command(label="Test archive", command=self.verify_archive)
        commands.add_command(label="View file", command=self.view_selected)
        commands.add_command(label="Delete", command=self.delete_selected)
        commands.add_separator()
        commands.add_command(label="Find...", command=self.find_entry, accelerator="Ctrl+F")
        commands.add_command(label="Repair archive...", command=self.repair_archive)
        commands.add_command(label="Archive comment...", command=self.edit_comment)
        menu.add_cascade(label="Commands", menu=commands)

        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Wizard...", command=self.create_new_archive)
        tools.add_command(label="Archive information", command=self.show_info)
        tools.add_command(label="Copy archive SHA-256", command=self.copy_archive_hash)
        menu.add_cascade(label="Tools", menu=tools)

        self.favorites_menu = tk.Menu(menu, tearoff=False)
        self.favorites_menu.add_command(label="Add current archive", command=self.add_favorite)
        self.favorites_menu.add_separator()
        self._refresh_favorites_menu()
        menu.add_cascade(label="Favorites", menu=self.favorites_menu)

        options = tk.Menu(menu, tearoff=False)
        options.add_command(label="ARK repair budget...", command=self.configure_repair_budget)
        menu.add_cascade(label="Options", menu=options)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About QBX", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self, bd=1, relief="raised", bg="#f0f0f0")
        toolbar.pack(fill="x")
        actions = [
            ("Add", lambda: self.add_to_archive(False), "#0a7f36"),
            ("Extract To", self.extract_archive, "#1d4ed8"),
            ("Test", self.verify_archive, "#7c3aed"),
            ("View", self.view_selected, "#0369a1"),
            ("Delete", self.delete_selected, "#b91c1c"),
            ("Find", self.find_entry, "#a16207"),
            ("Wizard", self.create_new_archive, "#6d28d9"),
            ("Info", self.show_info, "#334155"),
            ("Repair", self.repair_archive, "#be123c"),
        ]
        self.toolbar_buttons: list[tk.Button] = []
        for label, command, color in actions:
            b = tk.Button(
                toolbar,
                text=label,
                command=command,
                width=11,
                height=3,
                relief="flat",
                bg="#f0f0f0",
                fg=color,
                activebackground="#dbeafe",
                font=("Segoe UI", 9, "bold"),
            )
            b.pack(side="left", padx=1, pady=3)
            self.toolbar_buttons.append(b)

    def _set_busy(self, value: bool, message: str | None = None) -> None:
        self._busy = value
        for button in self.toolbar_buttons:
            button.configure(state="disabled" if value else "normal")
        self.configure(cursor="watch" if value else "")
        if message:
            self.status_var.set(message)

    def _run(self, message: str, fn, done=None) -> None:
        if self._busy:
            return
        self._set_busy(True, message)

        def worker():
            try:
                result = fn()
            except Exception as exc:
                self.after(0, lambda: self._task_error(exc))
                return
            self.after(0, lambda: self._task_done(result, done))

        threading.Thread(target=worker, daemon=True).start()

    def _task_error(self, exc: Exception) -> None:
        self._set_busy(False, "Failed")
        messagebox.showerror(APP_NAME, str(exc), parent=self)

    def _task_done(self, result, done) -> None:
        self._set_busy(False, "Ready")
        if done:
            done(result)

    def choose_archive(self) -> None:
        value = filedialog.askopenfilename(
            title="Open QBX archive",
            filetypes=[("QBX archives", "*.qbx"), ("All files", "*.*")],
        )
        if value:
            self.open_archive(Path(value))

    def open_archive(self, path: Path) -> None:
        def done(manifest: dict) -> None:
            self.archive_path = path
            self.manifest = manifest
            self.current_dir = PurePosixPath(".")
            self.title(f"{path.name} - QBX {__version__}")
            self._remember_recent(path)
            self.refresh_listing()

        self._run(f"Opening {path.name}...", lambda: inspect(path), done)

    def close_archive(self) -> None:
        self.archive_path = None
        self.manifest = None
        self.current_dir = PurePosixPath(".")
        self.item_paths.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.address_var.set("QBX\\")
        self.status_var.set("No archive open")
        self.title(f"QBX {__version__}")

    def create_new_archive(self) -> None:
        source = filedialog.askdirectory(title="Choose folder to archive")
        if not source:
            source = filedialog.askopenfilename(title="Choose file to archive")
        if not source:
            return
        output = filedialog.asksaveasfilename(
            title="Create QBX archive",
            defaultextension=".qbx",
            initialfile=Path(source).name + ".qbx",
            filetypes=[("QBX archives", "*.qbx")],
        )
        if not output:
            return
        comment = simpledialog.askstring("Archive comment", "Optional comment:", parent=self) or ""

        def done(result: dict) -> None:
            self.status_var.set(
                f"Created {human_bytes(result.get('archive', 0))} | "
                f"ARK edges {result.get('repair_edges', 0)}"
            )
            self.open_archive(Path(output))

        self._run(
            "Creating resilient QBX V3 archive...",
            lambda: pack(
                source,
                output,
                profile="resilient",
                repair_budget_pct=self.repair_budget_pct,
                comment=comment,
            ),
            done,
        )

    def refresh_archive(self) -> None:
        if self.archive_path:
            self.open_archive(self.archive_path)

    def refresh_listing(self) -> None:
        if not self.manifest:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_paths.clear()

        prefix = "" if str(self.current_dir) == "." else self.current_dir.as_posix().rstrip("/") + "/"
        child_dirs: set[str] = set()
        for directory in self.manifest.get("directories", []):
            if not directory.startswith(prefix):
                continue
            rest = directory[len(prefix):]
            if rest and "/" not in rest:
                child_dirs.add(rest)
        for entry in self.manifest.get("files", []):
            path = entry["path"]
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            if "/" in rest:
                child_dirs.add(rest.split("/", 1)[0])

        for name in sorted(child_dirs, key=str.casefold):
            full = prefix + name
            iid = self.tree.insert("", "end", values=(name, "", "", "Folder", "", ""))
            self.item_paths[iid] = full

        files = []
        for entry in self.manifest.get("files", []):
            path = entry["path"]
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            if "/" not in rest:
                files.append((rest, entry))
        for name, entry in sorted(files, key=lambda x: x[0].casefold()):
            modified = ""
            if isinstance(entry.get("mtime_ns"), int):
                try:
                    modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["mtime_ns"] / 1e9))
                except Exception:
                    pass
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    name,
                    human_bytes(entry["size"]),
                    len(entry.get("blocks", [])),
                    Path(name).suffix.lstrip(".").upper() or "File",
                    modified,
                    entry.get("sha256", "")[:16],
                ),
            )
            self.item_paths[iid] = entry["path"]

        display = prefix.replace("/", "\\")
        self.address_var.set(f"{self.archive_path or 'QBX'}\\{display}")
        stats = self.manifest.get("statistics", {})
        self.status_var.set(
            f"{len(self.manifest.get('files', []))} files | "
            f"{stats.get('unique_blocks', 0)} unique blocks | "
            f"{stats.get('repair_edges', 0)} ARK relations | "
            f"format V{self.manifest.get('version', '?')}"
        )

    def _double_click(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        path = self.item_paths.get(iid)
        if not path:
            return
        if self.tree.set(iid, "type") == "Folder":
            self.current_dir = PurePosixPath(path)
            self.refresh_listing()
        else:
            self.view_selected()

    def go_up(self) -> None:
        if str(self.current_dir) == ".":
            return
        parent = self.current_dir.parent
        self.current_dir = PurePosixPath(".") if str(parent) == "." else parent
        self.refresh_listing()

    def _selected_paths(self) -> list[str]:
        return [self.item_paths[i] for i in self.tree.selection() if i in self.item_paths]

    def add_to_archive(self, folder: bool = False) -> None:
        if not self.archive_path:
            self.create_new_archive()
            return
        if folder:
            value = filedialog.askdirectory(title="Add folder")
            sources = [value] if value else []
        else:
            sources = list(filedialog.askopenfilenames(title="Add files"))
        if not sources:
            return
        self._run(
            "Adding and rebuilding archive...",
            lambda: add_sources(
                self.archive_path,
                sources,
                overwrite_entries=True,
                repair_budget_pct=self.repair_budget_pct,
            ),
            lambda _r: self.refresh_archive(),
        )

    def extract_archive(self) -> None:
        if not self.archive_path:
            return
        destination = filedialog.askdirectory(title="Extract to")
        if not destination:
            return

        def done(result: dict) -> None:
            messagebox.showinfo(
                APP_NAME,
                f"Extraction complete.\n\nFiles: {result.get('files', 0)}\n"
                f"Data: {human_bytes(result.get('bytes', 0))}\n"
                f"Recovered blocks: {result.get('recovered_blocks', 0)}",
                parent=self,
            )

        self._run("Extracting and verifying...", lambda: unpack(self.archive_path, destination), done)

    def verify_archive(self) -> None:
        if not self.archive_path:
            return

        def done(result: dict) -> None:
            state = "HEALTHY"
            if result.get("degraded"):
                state = "DEGRADED BUT RECOVERABLE"
            messagebox.showinfo(
                APP_NAME,
                f"Archive test: {state}\n\n"
                f"Files: {result.get('files', 0)}\n"
                f"Blocks: {result.get('blocks', 0)}\n"
                f"Recovered blocks: {result.get('recovered_blocks', 0)}\n"
                f"Damaged records: {result.get('damaged_records', 0)}",
                parent=self,
            )

        self._run("Testing integrity and ARK recovery paths...", lambda: verify(self.archive_path), done)

    def view_selected(self) -> None:
        if not self.archive_path:
            return
        selected = self._selected_paths()
        if len(selected) != 1:
            messagebox.showwarning(APP_NAME, "Select exactly one file.", parent=self)
            return
        rel = selected[0]
        if not any(e["path"] == rel for e in (self.manifest or {}).get("files", [])):
            return

        def work():
            td = tempfile.mkdtemp(prefix="qbx-view-")
            self._temp_views.append(td)
            unpack(self.archive_path, td)
            return Path(td).joinpath(*PurePosixPath(rel).parts)

        def done(path: Path) -> None:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        self._run("Preparing preview...", work, done)

    def delete_selected(self) -> None:
        if not self.archive_path:
            return
        paths = self._selected_paths()
        if not paths or not messagebox.askyesno(APP_NAME, f"Delete {len(paths)} item(s)?", parent=self):
            return
        self._run(
            "Deleting and rebuilding archive...",
            lambda: delete_entries(self.archive_path, paths, repair_budget_pct=self.repair_budget_pct),
            lambda _r: self.refresh_archive(),
        )

    def find_entry(self) -> None:
        if not self.manifest:
            return
        term = simpledialog.askstring("Find", "Name or path contains:", parent=self)
        if not term:
            return
        match = next(
            (e for e in self.manifest.get("files", []) if term.casefold() in e["path"].casefold()),
            None,
        )
        if not match:
            messagebox.showinfo(APP_NAME, "No match found.", parent=self)
            return
        parent = PurePosixPath(match["path"]).parent
        self.current_dir = PurePosixPath(".") if str(parent) == "." else parent
        self.refresh_listing()
        target = PurePosixPath(match["path"]).name
        for iid in self.tree.get_children():
            if self.tree.set(iid, "name") == target:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                break

    def repair_archive(self) -> None:
        if not self.archive_path:
            return
        output = filedialog.asksaveasfilename(
            title="Save repaired QBX archive",
            defaultextension=".qbx",
            initialfile=self.archive_path.stem + "-repaired.qbx",
            filetypes=[("QBX archives", "*.qbx")],
        )
        if not output:
            return

        def done(result: dict) -> None:
            messagebox.showinfo(
                APP_NAME,
                f"Repair complete.\nRecovered blocks: {result.get('recovered_blocks', 0)}\n"
                f"SHA-256: {result.get('archive_sha256', '')}",
                parent=self,
            )
            self.open_archive(Path(output))

        self._run(
            "Rebuilding clean archive through ARK...",
            lambda: repair(self.archive_path, output, repair_budget_pct=self.repair_budget_pct),
            done,
        )

    def edit_comment(self) -> None:
        if not self.archive_path or not self.manifest:
            return
        value = simpledialog.askstring(
            "Archive comment",
            "Comment:",
            initialvalue=str(self.manifest.get("comment", "")),
            parent=self,
        )
        if value is None:
            return
        self._run(
            "Updating archive comment...",
            lambda: set_comment(self.archive_path, value, repair_budget_pct=self.repair_budget_pct),
            lambda _r: self.refresh_archive(),
        )

    def show_info(self) -> None:
        if not self.archive_path or not self.manifest:
            return
        stats = self.manifest.get("statistics", {})
        planner = self.manifest.get("planner", {})
        messagebox.showinfo(
            "QBX archive information",
            f"Archive: {self.archive_path}\n"
            f"Product: {self.manifest.get('product_version', __version__)}\n"
            f"Format: V{self.manifest.get('version')}\n"
            f"Profile: {self.manifest.get('compression_profile')}\n"
            f"Files: {stats.get('file_count', 0)}\n"
            f"Input: {human_bytes(stats.get('input_bytes', 0))}\n"
            f"Unique blocks: {stats.get('unique_blocks', 0)}\n"
            f"ARK relations: {stats.get('repair_edges', 0)}\n"
            f"Repair payload: {human_bytes(stats.get('repair_payload_bytes', 0))}\n"
            f"Planner: {planner.get('name', 'legacy')}\n"
            f"Comment: {self.manifest.get('comment', '') or '(none)'}",
            parent=self,
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
            self.clipboard_clear()
            self.clipboard_append(value)
            self.status_var.set("Archive SHA-256 copied")

        self._run("Calculating SHA-256...", work, done)

    def _remember_recent(self, path: Path) -> None:
        recent = [str(path)] + [x for x in self.config_data.get("recent", []) if x != str(path)]
        self.config_data["recent"] = recent[:10]
        self._save_config()

    def add_favorite(self) -> None:
        if not self.archive_path:
            return
        favorites = list(self.config_data.get("favorites", []))
        value = str(self.archive_path)
        if value not in favorites:
            favorites.append(value)
            self.config_data["favorites"] = favorites
            self._save_config()
            self._refresh_favorites_menu()

    def _refresh_favorites_menu(self) -> None:
        try:
            self.favorites_menu.delete(2, "end")
        except tk.TclError:
            pass
        favorites = self.config_data.get("favorites", []) if hasattr(self, "config_data") else []
        if not favorites:
            self.favorites_menu.add_command(label="(none)", state="disabled")
            return
        for value in favorites:
            self.favorites_menu.add_command(
                label=Path(value).name,
                command=lambda p=value: self.open_archive(Path(p)),
            )

    def configure_repair_budget(self) -> None:
        value = simpledialog.askfloat(
            "ARK repair budget",
            "Maximum repair payload as percent of primary payload (0-100):",
            initialvalue=self.repair_budget_pct,
            minvalue=0.0,
            maxvalue=100.0,
            parent=self,
        )
        if value is not None:
            self.repair_budget_pct = float(value)
            self.config_data["repair_budget_pct"] = self.repair_budget_pct
            self._save_config()

    def _sort_tree(self, column: str, reverse: bool) -> None:
        rows = [(self.tree.set(i, column), i) for i in self.tree.get_children("")]
        rows.sort(key=lambda pair: pair[0].casefold(), reverse=reverse)
        for index, (_value, iid) in enumerate(rows):
            self.tree.move(iid, "", index)
        self.tree.heading(column, command=lambda: self._sort_tree(column, not reverse))

    def show_about(self) -> None:
        messagebox.showinfo(
            "About QBX",
            f"QBX {__version__}\n\n"
            "Adaptive archive manager for Windows.\n"
            "V3 combines content-defined chunking, SHA-256 deduplication, AGRP global planning and ARK recoverability.\n\n"
            "The classic archive-manager UI uses original QBX branding and does not copy WinRAR proprietary assets.",
            parent=self,
        )

    def _on_close(self) -> None:
        for td in self._temp_views:
            shutil.rmtree(td, ignore_errors=True)
        self.destroy()


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
    if "--extract-here" in sys.argv:
        i = sys.argv.index("--extract-here")
        return 2 if i + 1 >= len(sys.argv) else _extract_here(sys.argv[i + 1])
    if "--create" in sys.argv:
        i = sys.argv.index("--create")
        return 2 if i + 1 >= len(sys.argv) else _create_from_shell(sys.argv[i + 1])

    initial = next(
        (a for a in sys.argv[1:] if not a.startswith("-") and a.lower().endswith(".qbx")),
        None,
    )
    app = QBXApp(initial_archive=initial)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
