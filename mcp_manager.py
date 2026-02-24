"""MCP Server Manager — starts MCP servers on demand and auto-stops when idle."""

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import config

logger = logging.getLogger("mcp_manager")

# How long (seconds) an MCP server can sit idle before being auto-stopped.
DEFAULT_IDLE_TIMEOUT = 300  # 5 minutes


@dataclass
class MCPServerEntry:
    """Registry entry for an MCP server."""
    name: str
    command: str
    args: list[str]
    cwd: str = str(config.VAULT_PATH)
    idle_timeout: int = DEFAULT_IDLE_TIMEOUT


@dataclass
class _RunningServer:
    """Tracks a running MCP server process and its idle timer."""
    entry: MCPServerEntry
    process: subprocess.Popen
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


class MCPManager:
    """Manages the lifecycle of MCP server processes.

    Usage:
        mgr = MCPManager()
        mgr.start("email-mcp")       # start on demand
        mgr.mark_active("email-mcp") # reset idle timer (call when server is used)
        mgr.stop("email-mcp")        # manual stop
        # or let the auto-reaper stop it after idle_timeout
    """

    def __init__(self):
        self._registry: dict[str, MCPServerEntry] = {}
        self._running: dict[str, _RunningServer] = {}
        self._lock = threading.Lock()
        self._reaper_running = False
        self._reaper_thread: threading.Thread | None = None

        # Auto-load servers from .claude/settings.json
        self._load_from_settings()

    # ── Registry ────────────────────────────────────────────────────────

    def _load_from_settings(self):
        """Load MCP server definitions from .claude/settings.json."""
        settings_path = config.VAULT_PATH / ".claude" / "settings.json"
        if not settings_path.exists():
            logger.warning("No .claude/settings.json found, MCP registry empty")
            return

        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                self.register(MCPServerEntry(
                    name=name,
                    command=cfg["command"],
                    args=cfg.get("args", []),
                    cwd=cfg.get("cwd", str(config.VAULT_PATH)),
                ))
            logger.info("Loaded %d MCP server(s) from settings: %s",
                        len(servers), list(servers.keys()))
        except Exception:
            logger.exception("Failed to load MCP servers from settings.json")

    def register(self, entry: MCPServerEntry):
        """Add or update an MCP server in the registry."""
        self._registry[entry.name] = entry
        logger.debug("Registered MCP server: %s", entry.name)

    def list_registered(self) -> list[str]:
        """Return names of all registered MCP servers."""
        return list(self._registry.keys())

    def list_running(self) -> list[str]:
        """Return names of all currently running MCP servers."""
        with self._lock:
            return [name for name, srv in self._running.items()
                    if srv.process.poll() is None]

    # ── Lifecycle ───────────────────────────────────────────────────────

    def start(self, name: str) -> bool:
        """Start an MCP server by name. Returns True if started (or already running)."""
        if name not in self._registry:
            logger.error("MCP server '%s' not in registry", name)
            return False

        with self._lock:
            # Already running?
            if name in self._running:
                srv = self._running[name]
                if srv.process.poll() is None:
                    logger.info("MCP server '%s' already running (PID %d)",
                                name, srv.process.pid)
                    srv.last_used = time.time()
                    return True
                # Process died, clean up
                del self._running[name]

            entry = self._registry[name]
            cmd = [entry.command, *entry.args]

            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=entry.cwd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                self._running[name] = _RunningServer(
                    entry=entry,
                    process=process,
                    last_used=time.time(),
                )
                logger.info("Started MCP server '%s' (PID %d)", name, process.pid)
            except FileNotFoundError:
                logger.error("Command not found for MCP server '%s': %s",
                             name, cmd)
                return False
            except Exception:
                logger.exception("Failed to start MCP server '%s'", name)
                return False

        # Ensure the idle reaper is running
        self._ensure_reaper()
        return True

    def stop(self, name: str) -> bool:
        """Stop a running MCP server. Returns True if stopped."""
        with self._lock:
            if name not in self._running:
                logger.debug("MCP server '%s' not running, nothing to stop", name)
                return False

            srv = self._running.pop(name)

        return self._terminate(srv)

    def stop_all(self):
        """Stop all running MCP servers."""
        with self._lock:
            servers = list(self._running.items())
            self._running.clear()

        for name, srv in servers:
            self._terminate(srv)
        logger.info("All MCP servers stopped")

    def _terminate(self, srv: _RunningServer) -> bool:
        """Terminate a server process gracefully, then forcefully."""
        name = srv.entry.name
        proc = srv.process
        if proc.poll() is not None:
            logger.debug("MCP server '%s' already exited (code %d)",
                         name, proc.returncode)
            return True

        logger.info("Stopping MCP server '%s' (PID %d)", name, proc.pid)
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MCP server '%s' didn't stop gracefully, killing",
                               name)
                proc.kill()
                proc.wait(timeout=3)
            logger.info("MCP server '%s' stopped", name)
            return True
        except Exception:
            logger.exception("Error stopping MCP server '%s'", name)
            return False

    # ── Activity tracking ───────────────────────────────────────────────

    def mark_active(self, name: str):
        """Reset the idle timer for a server (call when the server is being used)."""
        with self._lock:
            if name in self._running:
                self._running[name].last_used = time.time()

    def require(self, name: str) -> bool:
        """Ensure a server is running — start it if it isn't. Returns True on success."""
        with self._lock:
            if name in self._running and self._running[name].process.poll() is None:
                self._running[name].last_used = time.time()
                return True
        return self.start(name)

    # ── Idle reaper ─────────────────────────────────────────────────────

    def _ensure_reaper(self):
        """Start the background reaper thread if not already running."""
        if self._reaper_running:
            return
        self._reaper_running = True
        self._reaper_thread = threading.Thread(
            target=self._reaper_loop, daemon=True, name="mcp-reaper"
        )
        self._reaper_thread.start()
        logger.debug("MCP idle reaper started")

    def _reaper_loop(self):
        """Periodically check for idle servers and stop them."""
        while True:
            time.sleep(30)  # check every 30 seconds

            with self._lock:
                if not self._running:
                    self._reaper_running = False
                    logger.debug("MCP idle reaper exiting (no servers running)")
                    return

                now = time.time()
                to_stop = []
                for name, srv in self._running.items():
                    idle = now - srv.last_used
                    if idle >= srv.entry.idle_timeout and srv.process.poll() is None:
                        to_stop.append(name)

            for name in to_stop:
                logger.info("Auto-stopping idle MCP server '%s' (idle > %ds)",
                            name, self._registry[name].idle_timeout)
                self.stop(name)

    # ── Context manager for scoped usage ────────────────────────────────

    def scoped(self, name: str):
        """Context manager that starts a server on enter and stops on exit.

        Usage:
            with mgr.scoped("email-mcp"):
                # server is running
                do_email_stuff()
            # server is stopped
        """
        return _ScopedServer(self, name)

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return status of all registered servers."""
        result = {}
        with self._lock:
            for name, entry in self._registry.items():
                if name in self._running:
                    srv = self._running[name]
                    alive = srv.process.poll() is None
                    result[name] = {
                        "registered": True,
                        "running": alive,
                        "pid": srv.process.pid if alive else None,
                        "idle_seconds": round(time.time() - srv.last_used, 1),
                        "idle_timeout": entry.idle_timeout,
                    }
                else:
                    result[name] = {
                        "registered": True,
                        "running": False,
                        "pid": None,
                        "idle_seconds": None,
                        "idle_timeout": entry.idle_timeout,
                    }
        return result


class _ScopedServer:
    """Context manager for scoped MCP server lifecycle."""

    def __init__(self, mgr: MCPManager, name: str):
        self._mgr = mgr
        self._name = name

    def __enter__(self):
        if not self._mgr.start(self._name):
            raise RuntimeError(f"Failed to start MCP server '{self._name}'")
        return self._mgr

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mgr.stop(self._name)
        return False


# ── Module-level singleton ──────────────────────────────────────────────

_instance: MCPManager | None = None


def get_manager() -> MCPManager:
    """Get or create the global MCPManager singleton."""
    global _instance
    if _instance is None:
        _instance = MCPManager()
    return _instance


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    mgr = get_manager()

    print("Registered MCP servers:", mgr.list_registered())
    print("Status:", json.dumps(mgr.status(), indent=2))

    if mgr.list_registered():
        name = mgr.list_registered()[0]
        print(f"\nStarting '{name}'...")
        mgr.start(name)
        print("Running:", mgr.list_running())
        print("Status:", json.dumps(mgr.status(), indent=2))

        print(f"\nStopping '{name}'...")
        mgr.stop(name)
        print("Running:", mgr.list_running())
