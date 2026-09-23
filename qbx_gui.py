from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from qbx import __version__
from qbx.core import inspect, pack, unpack, verify


def human_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def self_test() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="qbx-gui-selftest-") as td:
            root = Path(td)
            src = root / "input"
            src.mkdir()
            (src / "hello.txt").write_text("QBX GUI SELF TEST\n" * 1000, encoding="utf-8")
            (src / "copy.txt").write_bytes((src / "hello.txt").read_bytes())

            archive = root / "selftest.qbx"
            out = root / "out"

            pack(src, archive, profile="balanced")
            result = verify(archive)
            if not result.get("ok"):
                return 2
            unpack(archive, out)

            expected = hashlib.sha256((src / "hello.txt").read_bytes()).hexdigest()
            actual = hashlib.sha256((out / "hello.txt").read_bytes()).hexdigest()
            return 0 if expected == actual else 3
    except Exception:
        return 1


class QBXApp(tk.Tk):
    def __init__(self, initial_archive: str | None = None):
        super().__init__()
        self.title(f"QBX {__version__}")
        self.geometry("940x680")
        self.minsize(820, 580)

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.profile_var = tk.StringVar(value="balanced")
        self.archive_var = tk.StringVar(value=initial_archive or "")
        self.destination_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto.")
        self._busy = False

        self._build_ui()

        if initial_archive:
            self.after(250, self.refresh_archive)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="QBX", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Arquivo adaptativo com deduplicação, compressão por bloco e verificação SHA-256",
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        create_tab = ttk.Frame(notebook, padding=14)
        open_tab = ttk.Frame(notebook, padding=14)
        notebook.add(create_tab, text="Criar arquivo")
        notebook.add(open_tab, text="Abrir arquivo")

        self._build_create_tab(create_tab)
        self._build_open_tab(open_tab)

        ttk.Label(
            root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=(8, 5),
        ).pack(fill="x", pady=(10, 0))

    def _row(self, parent, row, label, variable, buttons):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=(10, 8), pady=6
        )
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=2, sticky="e", pady=6)
        for text, command in buttons:
            ttk.Button(frame, text=text, command=command).pack(side="left", padx=2)

    def _build_create_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self._row(
            tab,
            0,
            "Origem",
            self.source_var,
            [("Arquivo", self.choose_source_file), ("Pasta", self.choose_source_folder)],
        )
        self._row(
            tab,
            1,
            "Destino .qbx",
            self.output_var,
            [("Escolher", self.choose_output)],
        )

        ttk.Label(tab, text="Perfil").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            tab,
            textvariable=self.profile_var,
            state="readonly",
            values=("fast", "balanced", "smallest"),
            width=16,
        ).grid(row=2, column=1, sticky="w", padx=(10, 8), pady=6)

        ttk.Label(
            tab,
            text="fast = velocidade • balanced = equilíbrio • smallest = menor tamanho",
        ).grid(row=3, column=1, sticky="w", padx=(10, 8), pady=(0, 12))

        self.create_button = ttk.Button(
            tab, text="Criar arquivo QBX", command=self.create_archive
        )
        self.create_button.grid(row=4, column=1, sticky="w", padx=(10, 8), pady=8)

        ttk.Separator(tab).grid(row=5, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(
            tab,
            text=(
                "O QBX divide o conteúdo em blocos, elimina blocos duplicados, "
                "escolhe RAW/Zstandard/Deflate/LZMA e registra SHA-256 para "
                "verificar a reconstrução."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w")

    def _build_open_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

        self._row(
            tab,
            0,
            "Arquivo .qbx",
            self.archive_var,
            [("Abrir", self.choose_archive)],
        )

        actions = ttk.Frame(tab)
        actions.grid(row=1, column=1, sticky="w", padx=(10, 8), pady=4)
        self.verify_button = ttk.Button(
            actions, text="Verificar integridade", command=self.verify_archive
        )
        self.verify_button.pack(side="left", padx=(0, 6))
        self.refresh_button = ttk.Button(
            actions, text="Atualizar lista", command=self.refresh_archive
        )
        self.refresh_button.pack(side="left")

        self._row(
            tab,
            2,
            "Extrair para",
            self.destination_var,
            [("Escolher", self.choose_destination)],
        )

        extract_actions = ttk.Frame(tab)
        extract_actions.grid(row=3, column=1, sticky="w", padx=(10, 8), pady=4)
        self.extract_button = ttk.Button(
            extract_actions, text="Extrair", command=self.extract_archive
        )
        self.extract_button.pack(side="left")

        columns = ("path", "size", "blocks")
        self.tree = ttk.Treeview(tab, columns=columns, show="headings")
        self.tree.heading("path", text="Arquivo")
        self.tree.heading("size", text="Tamanho")
        self.tree.heading("blocks", text="Blocos")
        self.tree.column("path", width=540)
        self.tree.column("size", width=120, anchor="e")
        self.tree.column("blocks", width=90, anchor="e")
        self.tree.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(14, 0))

        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=4, column=3, sticky="ns", pady=(14, 0))

    def _set_busy(self, value: bool, message: str | None = None):
        self._busy = value
        state = "disabled" if value else "normal"
        for widget in (
            self.create_button,
            self.verify_button,
            self.refresh_button,
            self.extract_button,
        ):
            widget.configure(state=state)
        if message:
            self.status_var.set(message)

    def _run(self, label, fn, on_success=None):
        if self._busy:
            return
        self._set_busy(True, label)

        def worker():
            try:
                result = fn()
            except Exception as exc:
                self.after(0, lambda: self._task_error(exc))
                return
            self.after(0, lambda: self._task_success(result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _task_error(self, exc):
        self._set_busy(False, "Falha.")
        messagebox.showerror("QBX", str(exc))

    def _task_success(self, result, on_success):
        self._set_busy(False, "Concluído.")
        if on_success:
            on_success(result)

    def choose_source_file(self):
        value = filedialog.askopenfilename(title="Escolha um arquivo")
        if value:
            self.source_var.set(value)
            if not self.output_var.get():
                self.output_var.set(value + ".qbx")

    def choose_source_folder(self):
        value = filedialog.askdirectory(title="Escolha uma pasta")
        if value:
            self.source_var.set(value)
            if not self.output_var.get():
                self.output_var.set(value.rstrip("/\\") + ".qbx")

    def choose_output(self):
        value = filedialog.asksaveasfilename(
            title="Salvar arquivo QBX",
            defaultextension=".qbx",
            filetypes=[("QBX Archive", "*.qbx"), ("Todos os arquivos", "*.*")],
        )
        if value:
            self.output_var.set(value)

    def choose_archive(self):
        value = filedialog.askopenfilename(
            title="Abrir arquivo QBX",
            filetypes=[("QBX Archive", "*.qbx"), ("Todos os arquivos", "*.*")],
        )
        if value:
            self.archive_var.set(value)
            if not self.destination_var.get():
                p = Path(value)
                self.destination_var.set(str(p.with_suffix("")) + "-extraido")
            self.refresh_archive()

    def choose_destination(self):
        value = filedialog.askdirectory(title="Escolha a pasta de destino")
        if value:
            self.destination_var.set(value)

    def create_archive(self):
        source = self.source_var.get().strip()
        output = self.output_var.get().strip()
        if not source or not output:
            messagebox.showwarning("QBX", "Escolha a origem e o arquivo de destino.")
            return

        def done(result):
            self.archive_var.set(output)
            self.status_var.set(
                f"Criado: {human_bytes(result['archive'])} • "
                f"{result['unique_chunks']} blocos únicos • "
                f"{result['deduplicated_chunks']} deduplicados"
            )
            messagebox.showinfo(
                "QBX",
                "Arquivo criado e pronto para verificação.\n\n"
                + json.dumps(result, indent=2, ensure_ascii=False),
            )

        self._run(
            "Criando arquivo QBX...",
            lambda: pack(source, output, profile=self.profile_var.get()),
            done,
        )

    def refresh_archive(self):
        archive = self.archive_var.get().strip()
        if not archive:
            return

        def done(manifest):
            for item in self.tree.get_children():
                self.tree.delete(item)
            for entry in manifest["files"]:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        entry["path"],
                        human_bytes(entry["size"]),
                        len(entry["blocks"]),
                    ),
                )
            stats = manifest["statistics"]
            self.status_var.set(
                f"{len(manifest['files'])} arquivos • "
                f"{stats['unique_blocks']} blocos únicos • "
                f"perfil {manifest['compression_profile']}"
            )

        self._run("Lendo arquivo QBX...", lambda: inspect(archive), done)

    def verify_archive(self):
        archive = self.archive_var.get().strip()
        if not archive:
            messagebox.showwarning("QBX", "Escolha um arquivo .qbx.")
            return

        def done(result):
            self.status_var.set(
                f"Integridade confirmada • {result['files']} arquivos • "
                f"{result['blocks']} blocos"
            )
            messagebox.showinfo(
                "QBX",
                "Integridade confirmada.\n\n"
                + json.dumps(result, indent=2, ensure_ascii=False),
            )

        self._run("Verificando todos os blocos...", lambda: verify(archive), done)

    def extract_archive(self):
        archive = self.archive_var.get().strip()
        destination = self.destination_var.get().strip()
        if not archive or not destination:
            messagebox.showwarning(
                "QBX", "Escolha o arquivo .qbx e a pasta de destino."
            )
            return

        def done(result):
            self.status_var.set(
                f"Extraído: {result['files']} arquivos • "
                f"{human_bytes(result['bytes'])}"
            )
            messagebox.showinfo("QBX", "Extração concluída e verificada.")

        self._run(
            "Extraindo e verificando...",
            lambda: unpack(archive, destination, overwrite=False),
            done,
        )


def main() -> int:
    if "--version" in sys.argv:
        print(f"QBX {__version__}")
        return 0
    if "--self-test" in sys.argv:
        return self_test()

    initial_archive = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and arg.lower().endswith(".qbx"):
            initial_archive = arg
            break

    app = QBXApp(initial_archive=initial_archive)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
