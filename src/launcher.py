"""Launcher: Host & Play or Join dialog for multiplayer Wager of War."""

import tkinter as tk
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Wager of War - Multiplayer Launcher")
        self.root.resizable(False, False)

        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack()

        tk.Label(frame, text="Wager of War", font=("Arial", 18, "bold")).pack(pady=(0, 15))

        # Host settings
        host_frame = tk.LabelFrame(frame, text="Connection", font=("Arial", 11), padx=10, pady=10)
        host_frame.pack(fill=tk.X, pady=5)

        row1 = tk.Frame(host_frame)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Host:", font=("Arial", 10), width=8, anchor="e").pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value="localhost")
        tk.Entry(row1, textvariable=self.host_var, font=("Arial", 10), width=20).pack(side=tk.LEFT, padx=5)

        row2 = tk.Frame(host_frame)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Port:", font=("Arial", 10), width=8, anchor="e").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8765")
        tk.Entry(row2, textvariable=self.port_var, font=("Arial", 10), width=20).pack(side=tk.LEFT, padx=5)

        row3 = tk.Frame(host_frame)
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Players:", font=("Arial", 10), width=8, anchor="e").pack(side=tk.LEFT)
        self.players_var = tk.StringVar(value="2")
        players_menu = tk.OptionMenu(row3, self.players_var, "2", "3", "4")
        players_menu.config(font=("Arial", 10))
        players_menu.pack(side=tk.LEFT, padx=5)

        row4 = tk.Frame(host_frame)
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="Name:", font=("Arial", 10), width=8, anchor="e").pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value="Player")
        tk.Entry(row4, textvariable=self.name_var, font=("Arial", 10), width=20).pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=15)

        tk.Button(btn_frame, text="Host & Play", font=("Arial", 12, "bold"),
                  command=self._host_and_play, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Join", font=("Arial", 12),
                  command=self._join, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Single Player", font=("Arial", 12),
                  command=self._single_player, width=12).pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.status_var, font=("Arial", 10), fg="gray").pack()

    def _host_and_play(self):
        """Start a server subprocess, then connect as a client."""
        port = self.port_var.get()
        players = self.players_var.get()

        # Start server in background
        server_script = os.path.join(os.path.dirname(__file__), "server.py")
        self._server_proc = subprocess.Popen(
            [sys.executable, server_script, "--players", players, "--port", port],
            cwd=os.path.dirname(__file__),
        )
        self.status_var.set(f"Server started on port {port}. Connecting...")
        self.root.after(500, self._connect_client)

    def _join(self):
        """Connect to an existing server."""
        self._connect_client()

    def _connect_client(self):
        """Create a GameClient and switch to overworld GUI."""
        from client import GameClient
        from overworld import OverworldGUI

        host = self.host_var.get()
        port = int(self.port_var.get())
        name = self.name_var.get()

        # Clear launcher widgets
        for w in self.root.winfo_children():
            w.destroy()

        # Create client and overworld
        client = GameClient(host, port, name, self.root, on_message=None)
        OverworldGUI(self.root, client=client)
        client.start()

    def _single_player(self):
        """Launch single-player overworld."""
        from overworld import OverworldGUI

        for w in self.root.winfo_children():
            w.destroy()

        OverworldGUI(self.root)

    def run(self):
        self.root.mainloop()


def main():
    app = LauncherGUI()
    app.run()


if __name__ == "__main__":
    main()
