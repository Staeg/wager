"""WebSocket client bridging network messages to tkinter via queue polling."""

import asyncio
import queue
import threading

import websockets

from .protocol import encode, decode


class GameClient:
    """Connects to a GameServer via WebSocket in a background thread.

    Messages from the server are placed in a queue.Queue.
    The tkinter main thread polls this queue via root.after().
    """

    def __init__(self, host, port, player_name, root, on_message):
        self.host = host
        self.port = port
        self.player_name = player_name
        self.root = root
        self.on_message = on_message
        self.player_id = None

        self._queue = queue.Queue()
        self._loop = None
        self._ws = None
        self._thread = None
        self._running = False

    def start(self):
        """Start the background thread and begin polling the queue."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._poll()

    def _run_loop(self):
        """Background thread: run asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    async def _connect(self):
        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                # Send join message
                await ws.send(encode({
                    "type": "join",
                    "player_name": self.player_name,
                }))
                async for raw in ws:
                    msg = decode(raw)
                    self._queue.put(msg)
        except Exception as e:
            self._queue.put({"type": "error", "message": f"Connection error: {e}"})

    def _poll(self):
        """Poll the message queue from the tkinter main thread."""
        while not self._queue.empty():
            try:
                msg = self._queue.get_nowait()
                self.on_message(msg)
            except queue.Empty:
                break
        if self._running:
            self.root.after(50, self._poll)

    def send(self, msg):
        """Thread-safe send: schedule on the asyncio loop."""
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(
                self._ws.send(encode(msg)),
                self._loop,
            )

    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
