#!/usr/bin/env python3
"""ACTAR Podman UI.

Interactive mode is a Textual TUI. CLI options remain available for scripts and
batch use. Run from the ACTAR host project directory.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

IMAGE = "actar"
CONTAINER = "running_actar"
CONFIG = Path("podman_actar_config.json")
LOG_FILE: Path | None = None
CONTAINER_ROOT = "/home/ubuntu/ACTAR/analysis_code/root_remote"
CONTAINER_DATA = "/home/ubuntu/data"
CONTAINER_OUTPUT = "/home/ubuntu/TrackOutput"
CONTAINER_INI = "/home/ubuntu/actar.ini"
COMPILE_STATUS_FILE = "podman_compile_result.txt"


def defaults() -> dict:
    base = Path.cwd()
    return {"root": str(base / "root"), "data": str(base / "DATA"),
            "output": str(base / "TrackOutput"), "actar_ini": str(base / "actar.ini"),
            "mount_root": True, "mount_data": True, "mount_output": True,
            "mount_actar_ini": True}


def load_config(path: Path) -> dict:
    config = defaults()
    if path.exists():
        try:
            config.update(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: ignoring invalid config {path}: {exc}", file=sys.stderr)
    # Existing paths are enabled automatically; missing paths are not mounted.
    config["mount_root"] = Path(config["root"]).expanduser().is_dir()
    config["mount_data"] = Path(config["data"]).expanduser().is_dir()
    config["mount_output"] = Path(config["output"]).expanduser().is_dir()
    config["mount_actar_ini"] = Path(config["actar_ini"]).expanduser().is_file()
    return config


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2) + "\n")


def init_log() -> Path:
    global LOG_FILE
    LOG_FILE = Path(__file__).resolve().parent / "podman_ui_actar.log"
    with LOG_FILE.open("a") as stream:
        stream.write("\n" + "=" * 78 + "\n")
        stream.write(f"ACTAR Podman log started {datetime.now().isoformat()}\n")
    return LOG_FILE


def log_line(text: str) -> None:
    if LOG_FILE is not None:
        with LOG_FILE.open("a") as stream:
            stream.write(f"[{datetime.now().isoformat()}] {text}\n")


def podman(*args: str, check: bool = True, capture: bool = False):
    command = ["podman", *args]
    log_line("COMMAND: " + shlex.join(command))
    try:
        result = subprocess.run(command, check=check, text=True,
                                capture_output=capture)
    except Exception as exc:
        log_line(f"EXCEPTION: {type(exc).__name__}: {exc}")
        raise
    if capture:
        if result.stdout:
            log_line("OUTPUT:\n" + result.stdout.rstrip())
        if result.stderr:
            log_line("STDERR:\n" + result.stderr.rstrip())
    log_line(f"RETURN CODE: {result.returncode}")
    return result


def expected_mounts(config: dict) -> list[tuple[str, str, bool]]:
    mounts = []
    if config["mount_root"]:
        mounts.append((str(Path(config["root"]).expanduser().resolve()), CONTAINER_ROOT, True))
    if config["mount_data"]:
        mounts.append((str(Path(config["data"]).expanduser().resolve()), CONTAINER_DATA, False))
    if config["mount_output"]:
        mounts.append((str(Path(config["output"]).expanduser().resolve()), CONTAINER_OUTPUT, True))
    if config["mount_actar_ini"]:
        mounts.append((str(Path(config["actar_ini"]).expanduser().resolve()), CONTAINER_INI, False))
    return mounts


def image_exists() -> bool:
    return podman("image", "exists", IMAGE, check=False, capture=True).returncode == 0


def is_running() -> bool:
    result = podman("ps", "--format", "{{.Names}}", check=False, capture=True)
    return result.returncode == 0 and CONTAINER in result.stdout.splitlines()


def compilation_status(config: dict) -> tuple[str, str]:
    path = Path(config["root"]).expanduser() / COMPILE_STATUS_FILE
    if not path.is_file():
        return "[red]✗ no result[/red]", "No compilation result"
    try:
        state = path.read_text().split()[0].upper()
    except OSError:
        return "[red]✗ unreadable[/red]", "Compilation result unreadable"
    if state == "OK":
        return "[green]✓ OK[/green]", "Last compilation OK"
    if state == "RUNNING":
        return "[yellow]… running[/yellow]", "Compilation running"
    if state == "FAIL":
        return "[red]✗ FAIL[/red]", "Last compilation failed"
    return "[red]✗ unknown[/red]", "Unknown compilation result"


def running_with_shares(config: dict) -> tuple[bool, str]:
    if not is_running():
        return False, "Container stopped"
    result = podman("inspect", CONTAINER, check=False, capture=True)
    if result.returncode:
        return False, "Container running; mounts unavailable"
    try:
        actual = json.loads(result.stdout)[0].get("Mounts", [])
    except (ValueError, IndexError):
        return False, "Container running; mounts unavailable"
    for source, destination, writable in expected_mounts(config):
        matches = [m for m in actual if m.get("Destination") == destination]
        if not matches or str(Path(matches[0].get("Source", "")).resolve()) != source:
            return False, "Running with different shares"
        if bool(matches[0].get("RW", False)) != writable:
            return False, "Running with different share modes"
    return True, "Running with selected shares"


def validate(config: dict, create_dirs: bool = True) -> None:
    for flag, key in (("mount_root", "root"), ("mount_data", "data"),
                      ("mount_output", "output"), ("mount_actar_ini", "actar_ini")):
        if not config[flag]:
            continue
        path = Path(config[key]).expanduser()
        if key == "actar_ini":
            if not path.is_file():
                raise SystemExit(f"Required file does not exist: {path}")
        elif create_dirs:
            path.mkdir(parents=True, exist_ok=True)
        elif not path.is_dir():
            raise SystemExit(f"Required directory does not exist: {path}")
        config[key] = str(path.resolve())


def volume_args(config: dict) -> list[str]:
    args = []
    for source, destination, writable in expected_mounts(config):
        mode = ":Z" if writable else ":ro,Z"
        args += ["-v", f"{source}:{destination}{mode}"]
    return args


def start_container(config: dict) -> None:
    validate(config)
    image_check = podman("image", "exists", IMAGE, check=False, capture=True)
    if image_check.returncode != 0:
        warning = f"Image '{IMAGE}' was not found. Build it explicitly with ./podman_build_actar.sh."
        print(f"WARNING: {warning}")
        log_line("WARNING: " + warning)
        raise SystemExit(f"{warning} See {LOG_FILE}")
    if is_running():
        podman("stop", CONTAINER, check=False, capture=True)
    args = ["run", "--rm", "--detach", "--userns=keep-id", "--name", CONTAINER]
    result = podman(*(args + volume_args(config) + [IMAGE, "sleep", "infinity"]), capture=True)
    if result.returncode != 0:
        raise SystemExit(f"Podman failed to start the container; see {LOG_FILE}")


def build_image() -> None:
    log_line("Explicit image build requested by user")
    result = podman("build", "-f", "podman_dockerfile_actar", "-t", IMAGE, ".",
                    check=False, capture=True)
    if result.returncode != 0:
        raise SystemExit(f"Image build failed; see {LOG_FILE}")


def stop_container() -> None:
    podman("stop", CONTAINER, check=False)


def exec_analysis(config: dict, run: str | None, compile_only: bool,
                  start_event: int, number_events: int) -> None:
    validate(config)
    if not is_running():
        start_container(config)
    command = "source /home/ubuntu/root/bin/thisroot.sh && cd " + shlex.quote(CONTAINER_ROOT) + " && make"
    if run is not None and not compile_only:
        command += " && make run run=" + shlex.quote(run)
        if run != "277" or start_event != 0 or number_events != 10:
            command += f" start_event={start_event} number_of_events={number_events}"
    podman("exec", "-it", CONTAINER, "bash", "-lc", command)


# ------------------------------ Textual UI ------------------------------

def launch_ui(config_path: Path) -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, ListItem, ListView, Static
        from textual.screen import ModalScreen
    except ImportError:
        raise SystemExit("The interactive UI requires Textual. Install it with: uv tool install --editable .")

    class PathPicker(ModalScreen[str | None]):
        def __init__(self, initial: str, want_file: bool, title: str):
            super().__init__()
            self.current = Path(initial).expanduser()
            self.want_file = want_file
            self.title_text = title
            if want_file and self.current.is_file():
                self.current = self.current.parent
            if not self.current.is_dir():
                self.current = Path.cwd()

        def compose(self) -> ComposeResult:
            yield Vertical(Label(self.title_text, id="picker-title"),
                           Label("Directories only; INI files only for actar.ini. Type a path below if needed.", id="picker-help"),
                           Label(id="picker-current"), ListView(id="picker-list"),
                           Input(placeholder="Complete path", id="path-input"),
                           Horizontal(Button("Select current", id="pick-current"),
                                      Button("Cancel", id="pick-cancel")))

        def on_mount(self) -> None:
            self.run_worker(self.refresh_listing())

        async def refresh_listing(self) -> None:
            self.query_one("#picker-current", Label).update(str(self.current))
            listing = self.query_one("#picker-list", ListView)
            # ListView.clear() schedules removal; await removal before adding
            # children, otherwise Textual can report duplicate IDs on refresh.
            await listing.remove_children()
            if self.current.parent != self.current:
                listing.append(ListItem(Label(".."), id="parent"))
            try:
                all_entries = list(self.current.iterdir())
                if self.want_file:
                    # File shares show only INI files, while directories remain
                    # visible so the user can navigate to the file.
                    entries = [p for p in all_entries if p.is_dir() or p.suffix.lower() == ".ini"]
                else:
                    # Directory shares never show ordinary files.
                    entries = [p for p in all_entries if p.is_dir()]
                entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
            except OSError as exc:
                listing.append(ListItem(Label(f"Cannot read directory: {exc}")))
                return
            for index, entry in enumerate(entries):
                kind = "[DIR] " if entry.is_dir() else "[FILE]"
                listing.append(ListItem(Label(f"{kind} {entry.name}"), id=f"entry-{index}"))
            self.entries = entries

        async def on_list_view_selected(self, event: ListView.Selected) -> None:
            item_id = event.item.id or ""
            if item_id == "parent":
                self.current = self.current.parent
                await self.refresh_listing()
                return
            if not item_id.startswith("entry-"):
                return
            entry = self.entries[int(item_id.split("-")[-1])]
            if entry.is_dir():
                self.current = entry
                await self.refresh_listing()
            elif self.want_file:
                self.dismiss(str(entry.resolve()))

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "pick-cancel":
                self.dismiss(None)
            elif event.button.id == "pick-current" and not self.want_file:
                self.dismiss(str(self.current.resolve()))

        def on_input_submitted(self, event: Input.Submitted) -> None:
            candidate = Path(event.value).expanduser()
            if (self.want_file and candidate.is_file()) or (not self.want_file and candidate.is_dir()):
                self.dismiss(str(candidate.resolve()))
            else:
                self.query_one("#picker-help", Label).update("[red]Path does not exist or has the wrong type.[/red]")

    class ConfirmQuit(ModalScreen[bool | None]):
        def compose(self) -> ComposeResult:
            yield Vertical(Label("Stop and remove the running ACTAR container before quitting?"),
                           Label("Choose No to leave it running."),
                           Horizontal(Button("Yes, stop and remove", id="confirm-yes"),
                                      Button("No, leave running", id="confirm-no"),
                                      Button("Cancel", id="confirm-cancel")))

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(True if event.button.id == "confirm-yes" else
                         False if event.button.id == "confirm-no" else None)

    class ActarApp(App):
        CSS = """
        Screen { layout: vertical; }
        #status { height: 3; padding: 1; text-style: bold; }
        #status Label { width: 1fr; }
        #shares { height: 1fr; }
        #actions { height: 3; align: center middle; }
        #actions Button { margin: 0 1; }
        #hint { height: 2; padding: 0 1; }
        #connect-hint { height: 2; padding: 0 1; color: $text-muted; }
        #compile-hint { height: 2; padding: 0 1; color: $text-muted; }
        ConfirmQuit { align: center middle; }
        ConfirmQuit > Vertical { width: 70; height: auto; padding: 2; border: thick $accent; background: $surface; }
        ConfirmQuit Button { margin: 1 1 0 0; }
        """
        BINDINGS = [("q", "request_quit", "Quit")]

        def __init__(self):
            super().__init__()
            self.config = load_config(config_path)
            self.share_rows = [("root", "mount_root", False), ("DATA", "mount_data", False),
                               ("output", "mount_output", False), ("actar.ini", "mount_actar_ini", True)]
            self.selected_key = "root"

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Horizontal(Label(id="image-status"), Label(id="container-status"), Label(id="compile-status"), id="status")
            yield DataTable(id="shares")
            yield Label("Select a share and press e to edit its host path. Missing paths are red.", id="hint")
            yield Label("Connect manually: podman exec -it running_actar bash", id="connect-hint")
            yield Label("Compile/run help: cd root && ../podman_compile_and_run_actar.sh -h", id="compile-hint")
            yield Horizontal(Button("Start / Restart", id="start"), Button("Stop", id="stop"),
                             Button("Save", id="save"), Button("Quit", id="quit"), id="actions")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#shares", DataTable)
            table.add_columns("Share name", "Host path", "Status", "Container path", "Mode")
            self.refresh_ui()
            self.set_interval(2.0, self.refresh_ui)

        def refresh_ui(self) -> None:
            table = self.query_one("#shares", DataTable)
            table.clear()
            targets = {"root": (CONTAINER_ROOT, "rw"), "DATA": (CONTAINER_DATA, "ro"),
                       "output": (CONTAINER_OUTPUT, "rw"), "actar.ini": (CONTAINER_INI, "ro")}
            for name, flag, want_file in self.share_rows:
                key = "actar_ini" if name == "actar.ini" else name.lower()
                path = Path(self.config[key]).expanduser()
                exists = path.is_file() if want_file else path.is_dir()
                status = "[green]OK[/green]" if exists else "[red]MISSING[/red]"
                table.add_row(name, str(path), status, targets[name][0], targets[name][1], key=name)
            image_ok = image_exists()
            container_ok = is_running()
            compile_label, _ = compilation_status(self.config)
            self.query_one("#image-status", Label).update(
                f"[green]● image '{IMAGE}' exists[/green]" if image_ok else
                f"[red]● image '{IMAGE}' missing[/red]")
            self.query_one("#container-status", Label).update(
                f"[green]● container '{CONTAINER}' runs[/green]" if container_ok else
                f"[red]● container '{CONTAINER}' stopped[/red]")
            self.query_one("#compile-status", Label).update(
                f"● compilation: {compile_label}")

        def on_key(self, event) -> None:
            if event.key == "e" and isinstance(self.focused, DataTable):
                self.edit_selected()
                event.stop()

        def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
            row = self.share_rows[event.coordinate.row]
            self.selected_key = "actar_ini" if row[0] == "actar.ini" else row[0].lower()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self.selected_key = "actar_ini" if event.row_key.value == "actar.ini" else str(event.row_key.value).lower()
            self.edit_selected()

        def edit_selected(self) -> None:
            for name, flag, want_file in self.share_rows:
                key = "actar_ini" if name == "actar.ini" else name.lower()
                if key == self.selected_key:
                    self.push_screen(PathPicker(self.config[key], want_file, f"Choose {name} host path"),
                                     lambda result: self.path_selected(key, result))
                    return

        def path_selected(self, key: str, result: str | None) -> None:
            if result:
                self.config[key] = result
                self.refresh_ui()

        def action_request_quit(self) -> None:
            if not is_running():
                self.exit()
                return
            self.push_screen(ConfirmQuit(), self.quit_confirmed)

        def quit_confirmed(self, remove_container: bool | None) -> None:
            if remove_container is None:
                return
            if remove_container:
                stop_container()
            self.exit()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "quit":
                self.action_request_quit()
            elif event.button.id == "save":
                save_config(config_path, self.config)
                self.notify(f"Saved {config_path}")
            elif event.button.id == "start":
                try:
                    if podman("image", "exists", IMAGE, check=False, capture=True).returncode != 0:
                        self.notify("Image 'actar' not found. Build it explicitly with podman-ui-actar --build.", severity="warning")
                        return
                    start_container(self.config)
                    self.notify("Container started with selected shares")
                except (SystemExit, subprocess.CalledProcessError) as exc:
                    self.notify(f"{exc}  Log: {LOG_FILE}", severity="error")
                self.refresh_ui()
            elif event.button.id == "stop":
                stop_container()
                self.notify("Container stopped")
                self.refresh_ui()

    ActarApp().run()


def main() -> int:
    parser = argparse.ArgumentParser(description="ACTAR Podman UI")
    parser.add_argument("run", nargs="?", help="run number; omit for UI")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--build", action="store_true", help="explicitly build the image")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("-c", "--compile-only", action="store_true")
    parser.add_argument("-s", "--start-event", type=int, default=0)
    parser.add_argument("-n", "--number-of-events", type=int, default=10)
    args = parser.parse_args()
    init_log()
    log_line("Arguments: " + shlex.join(sys.argv[1:]))
    config = load_config(args.config)
    if args.stop:
        stop_container(); return 0
    if args.build:
        build_image(); return 0
    if args.start:
        start_container(config); return 0
    if args.shell:
        start_container(config); podman("exec", "-it", CONTAINER, "bash"); return 0
    if args.run or args.compile_only:
        exec_analysis(config, args.run, args.compile_only, args.start_event, args.number_of_events); return 0
    launch_ui(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
