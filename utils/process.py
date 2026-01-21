"""Process management utilities for LOOT RUN server.

Provides cross-platform file locking to prevent multiple server instances
and properly manage server lifecycle.
"""

import os
import sys
import socket
import time
from pathlib import Path
from typing import Optional


class ServerLock:
    """Cross-platform file lock for server process management.

    Uses file locking to ensure only one server instance runs at a time.
    The lock is automatically released when the process exits (even on crash).

    Usage:
        lock = ServerLock(port=8765)
        if not lock.acquire():
            print(f"Server already running (PID: {lock.get_existing_pid()})")
            sys.exit(1)
        # ... run server ...
        # Lock is automatically released on exit
    """

    def __init__(self, port: int, lock_dir: Optional[Path] = None):
        """Initialize server lock.

        Args:
            port: Server port number (used in lock file name)
            lock_dir: Directory for lock file. Defaults to temp directory.
        """
        self.port = port

        if lock_dir is None:
            # Use temp directory for lock files
            if sys.platform == 'win32':
                lock_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '.')))
            else:
                lock_dir = Path('/tmp')

        self.lock_dir = Path(lock_dir)
        self.lock_file = self.lock_dir / f'lootrun_server_{port}.lock'
        self._file_handle = None
        self._locked = False

    def acquire(self) -> bool:
        """Try to acquire the server lock.

        Returns:
            True if lock acquired, False if another instance holds it.
        """
        try:
            # Create lock directory if needed
            self.lock_dir.mkdir(parents=True, exist_ok=True)

            # Open file for writing (create if doesn't exist)
            self._file_handle = open(self.lock_file, 'w')

            # Try to acquire exclusive lock
            if sys.platform == 'win32':
                # Windows: use msvcrt
                import msvcrt
                try:
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    self._locked = True
                except (IOError, OSError):
                    self._file_handle.close()
                    self._file_handle = None
                    return False
            else:
                # Unix: use fcntl
                import fcntl
                try:
                    fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._locked = True
                except (IOError, OSError):
                    self._file_handle.close()
                    self._file_handle = None
                    return False

            # Write PID to lock file (informational)
            self._file_handle.write(str(os.getpid()))
            self._file_handle.flush()

            return True

        except Exception:
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            return False

    def release(self):
        """Release the server lock.

        Note: Lock is automatically released when process exits.
        This method is for explicit cleanup if needed.
        """
        if self._file_handle:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    try:
                        msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except (IOError, OSError):
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                    except (IOError, OSError):
                        pass
                self._file_handle.close()
            except Exception:
                pass
            finally:
                self._file_handle = None
                self._locked = False

    def get_existing_pid(self) -> Optional[int]:
        """Get PID from existing lock file (if any).

        Returns:
            PID of existing server, or None if can't determine.
        """
        try:
            if self.lock_file.exists():
                content = self.lock_file.read_text().strip()
                if content:
                    return int(content)
        except (ValueError, IOError, OSError):
            pass
        return None

    def is_locked(self) -> bool:
        """Check if we currently hold the lock."""
        return self._locked

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise RuntimeError(f"Could not acquire server lock for port {self.port}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False


def wait_for_server(port: int, host: str = '127.0.0.1', timeout: float = 5.0) -> bool:
    """Wait for server to start accepting connections.

    Args:
        port: Server port
        host: Server host
        timeout: Maximum time to wait in seconds

    Returns:
        True if server is ready, False if timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def is_server_running(port: int, host: str = '127.0.0.1') -> bool:
    """Check if a server is accepting connections on the given port.

    Args:
        port: Server port
        host: Server host

    Returns:
        True if server is listening, False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False
