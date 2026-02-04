"""Launcher: Host & Play or Join dialog for multiplayer Wager of War."""

import tkinter as tk
import subprocess
import sys
import os
from .compat import setup_frozen_path

setup_frozen_path()


class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Wager of War - Multiplayer Launcher")
        self.root.resizable(False, False)
        self._server_proc = None
        self.upgrade_mode_var = tk.StringVar(value="none")
        self.ai_mode_var = tk.StringVar(value="inactive")

        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack()

        tk.Label(frame, text="Wager of War", font=("Arial", 18, "bold")).pack(
            pady=(0, 15)
        )

        # Host settings
        host_frame = tk.LabelFrame(
            frame, text="Connection", font=("Arial", 11), padx=10, pady=10
        )
        host_frame.pack(fill=tk.X, pady=5)

        row1 = tk.Frame(host_frame)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Host:", font=("Arial", 10), width=8, anchor="e").pack(
            side=tk.LEFT
        )
        self.host_var = tk.StringVar(value="localhost")
        tk.Entry(row1, textvariable=self.host_var, font=("Arial", 10), width=20).pack(
            side=tk.LEFT, padx=5
        )

        row2 = tk.Frame(host_frame)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Port:", font=("Arial", 10), width=8, anchor="e").pack(
            side=tk.LEFT
        )
        self.port_var = tk.StringVar(value="8765")
        tk.Entry(row2, textvariable=self.port_var, font=("Arial", 10), width=20).pack(
            side=tk.LEFT, padx=5
        )

        row3 = tk.Frame(host_frame)
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Players:", font=("Arial", 10), width=8, anchor="e").pack(
            side=tk.LEFT
        )
        self.players_var = tk.StringVar(value="2")
        players_menu = tk.OptionMenu(row3, self.players_var, "2", "3", "4")
        players_menu.config(font=("Arial", 10))
        players_menu.pack(side=tk.LEFT, padx=5)

        row4 = tk.Frame(host_frame)
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="Name:", font=("Arial", 10), width=8, anchor="e").pack(
            side=tk.LEFT
        )
        self.name_var = tk.StringVar(value="Player")
        tk.Entry(row4, textvariable=self.name_var, font=("Arial", 10), width=20).pack(
            side=tk.LEFT, padx=5
        )

        upgrades_frame = tk.LabelFrame(
            frame, text="Starting Upgrades", font=("Arial", 11), padx=10, pady=8
        )
        upgrades_frame.pack(fill=tk.X, pady=8)
        tk.Radiobutton(
            upgrades_frame,
            text="No upgrades",
            variable=self.upgrade_mode_var,
            value="none",
            font=("Arial", 10),
        ).pack(anchor="w")
        tk.Radiobutton(
            upgrades_frame,
            text="Random upgrade",
            variable=self.upgrade_mode_var,
            value="random",
            font=("Arial", 10),
        ).pack(anchor="w")
        tk.Radiobutton(
            upgrades_frame,
            text="Choose upgrade",
            variable=self.upgrade_mode_var,
            value="choose",
            font=("Arial", 10),
        ).pack(anchor="w")

        # AI Mode selection (for single-player)
        ai_frame = tk.LabelFrame(
            frame, text="AI Mode (Single Player)", font=("Arial", 11), padx=10, pady=8
        )
        ai_frame.pack(fill=tk.X, pady=8)
        tk.Radiobutton(
            ai_frame,
            text="Inactive (build once, no actions)",
            variable=self.ai_mode_var,
            value="inactive",
            font=("Arial", 10),
        ).pack(anchor="w")
        tk.Radiobutton(
            ai_frame,
            text="Passive (rebuild every 3-7 turns)",
            variable=self.ai_mode_var,
            value="passive",
            font=("Arial", 10),
        ).pack(anchor="w")
        tk.Radiobutton(
            ai_frame,
            text="Aggressive (hunt and attack)",
            variable=self.ai_mode_var,
            value="aggressive",
            font=("Arial", 10),
        ).pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=15)

        tk.Button(
            btn_frame,
            text="Host & Play",
            font=("Arial", 12, "bold"),
            command=self._host_and_play,
            width=12,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame, text="Join", font=("Arial", 12), command=self._join, width=12
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame,
            text="Single Player",
            font=("Arial", 12),
            command=self._single_player,
            width=12,
        ).pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="")
        tk.Label(
            frame, textvariable=self.status_var, font=("Arial", 10), fg="gray"
        ).pack()

        # Server status bar (hidden until a server is started)
        self._server_frame = tk.Frame(frame)
        self._server_status_var = tk.StringVar(value="")
        self._server_indicator = tk.Label(
            self._server_frame,
            textvariable=self._server_status_var,
            font=("Arial", 10, "bold"),
            fg="green",
        )
        self._server_indicator.pack(side=tk.LEFT, padx=5)
        self._stop_btn = tk.Button(
            self._server_frame,
            text="Stop Server",
            font=("Arial", 10),
            command=self._stop_server,
            fg="red",
        )
        self._stop_btn.pack(side=tk.LEFT, padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _find_server_exe(self):
        """Locate the wager-server executable next to the launcher."""
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            server_exe = os.path.join(exe_dir, "wager-server.exe")
            if os.path.isfile(server_exe):
                return [server_exe]
        # Non-frozen: run server module with Python
        return [sys.executable, "-m", "src.server"]

    def _host_and_play(self):
        """Start a server subprocess, then connect as a client."""
        port = self.port_var.get()
        players = self.players_var.get()
        upgrade_mode = self.upgrade_mode_var.get()

        cmd = self._find_server_exe() + [
            "--players",
            players,
            "--port",
            port,
            "--upgrade-mode",
            upgrade_mode,
        ]
        self._server_proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32"
            else 0,
        )
        self._server_frame.pack(fill=tk.X, pady=5)
        self._server_status_var.set(f"Server running (port {port})")
        self._server_indicator.config(fg="green")
        self._poll_server()

        self.status_var.set(f"Server started on port {port}. Connecting...")
        self.root.after(500, self._connect_client)

    def _poll_server(self):
        """Periodically check if the server process is still alive."""
        if self._server_proc is None:
            return
        rc = self._server_proc.poll()
        if rc is not None:
            self._server_proc = None
            if self._server_indicator.winfo_exists():
                self._server_status_var.set(f"Server stopped (exit code {rc})")
                self._server_indicator.config(fg="red")
        else:
            self.root.after(1000, self._poll_server)

    def _stop_server(self):
        """Terminate the server process."""
        if self._server_proc is not None:
            self._server_proc.terminate()
            self._server_proc.wait()
            self._server_proc = None
        if self._server_indicator.winfo_exists():
            self._server_status_var.set("Server stopped")
            self._server_indicator.config(fg="red")

    def _on_close(self):
        """Clean up server process on window close."""
        if self._server_proc is not None:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
        self.root.destroy()

    def _join(self):
        """Connect to an existing server."""
        self._connect_client()

    def _connect_client(self):
        """Create a GameClient and switch to overworld GUI."""
        from .client import GameClient
        from .overworld_gui import OverworldGUI

        host = self.host_var.get()
        port = int(self.port_var.get())
        name = self.name_var.get()
        upgrade_mode = self.upgrade_mode_var.get()

        # Clear launcher widgets
        for w in self.root.winfo_children():
            w.destroy()

        # Create client and overworld
        client = GameClient(host, port, name, self.root, on_message=None)
        OverworldGUI(self.root, client=client, upgrade_mode=upgrade_mode)
        client.start()

    def _single_player(self):
        """Launch single-player overworld."""
        from .overworld_gui import OverworldGUI

        for w in self.root.winfo_children():
            w.destroy()

        OverworldGUI(
            self.root,
            upgrade_mode=self.upgrade_mode_var.get(),
            ai_mode=self.ai_mode_var.get(),
        )

    def run(self):
        self.root.mainloop()


def main():
    app = LauncherGUI()
    app.run()


if __name__ == "__main__":
    main()
