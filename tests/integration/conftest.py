"""Shared fixtures and utilities for integration tests."""

import platform
import socket
import subprocess
import sys
import time

import pytest


def kill_process_on_port(port: int) -> None:
    """Kill any process listening on the specified port.

    This prevents zombie processes from previous test runs from blocking new tests.
    """
    try:
        # Check if port is in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()

        if result != 0:
            return  # Port not in use

        # Port is in use - find and kill the process
        if platform.system() == 'Windows':
            # Get PID using netstat
            try:
                output = subprocess.check_output(
                    f'netstat -ano | findstr ":{port}"',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode()

                for line in output.strip().split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        pid = parts[-1]
                        subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            check=False,
                            capture_output=True
                        )
            except Exception:
                pass
        else:
            # Unix-like systems - try multiple methods
            # Method 1: lsof
            try:
                output = subprocess.check_output(
                    f'lsof -ti:{port}',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode()
                for pid in output.strip().split('\n'):
                    if pid:
                        subprocess.run(['kill', '-9', pid], check=False, capture_output=True)
            except subprocess.CalledProcessError:
                pass
            except FileNotFoundError:
                pass

            # Method 2: fuser (fallback)
            try:
                subprocess.run(
                    f'fuser -k {port}/tcp',
                    shell=True,
                    check=False,
                    capture_output=True
                )
            except Exception:
                pass

        # Wait for port to be released
        time.sleep(0.5)
    except Exception:
        pass  # Best effort - don't fail tests if cleanup fails


def wait_for_server(port: int, timeout: float = 5.0) -> bool:
    """Wait for server to start accepting connections.

    Returns True if server is ready, False if timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def create_server_fixture(port: int):
    """Factory function to create a server fixture for a given port."""
    @pytest.fixture
    def server_fixture():
        kill_process_on_port(port)

        # Capture stderr to diagnose startup failures
        proc = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to be ready (with longer timeout for CI)
        # CI environments (especially Linux runners) can be slower to start
        if not wait_for_server(port, timeout=15.0):
            # Server didn't start - check if process is still running
            poll_result = proc.poll()
            if poll_result is not None:
                # Process exited - capture stderr to understand why
                try:
                    _, stderr = proc.communicate(timeout=2)
                    stderr_text = stderr.decode().strip() if stderr else "No stderr"
                except Exception:
                    stderr_text = "Could not capture stderr"
                error_msg = f"Server process exited with code {poll_result}. stderr: {stderr_text}"
            else:
                error_msg = "Server did not start accepting connections in time"
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            pytest.fail(f"Server failed to start on port {port}: {error_msg}")

        yield proc

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    return server_fixture


# Pre-create fixtures for commonly used ports
server_process_18765 = create_server_fixture(18765)
server_process_18766 = create_server_fixture(18766)
server_process_18767 = create_server_fixture(18767)
server_process_18770 = create_server_fixture(18770)
server_process_18771 = create_server_fixture(18771)
server_process_18780 = create_server_fixture(18780)
server_process_18781 = create_server_fixture(18781)
