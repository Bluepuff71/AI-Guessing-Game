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
            output = subprocess.check_output(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode()

            for line in output.strip().split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    pid = parts[-1]
                    try:
                        subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            check=False,
                            capture_output=True
                        )
                    except Exception:
                        pass
        else:
            # Unix-like systems
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
                pass  # No process found

        # Wait for port to be released
        time.sleep(0.3)
    except Exception:
        pass  # Best effort - don't fail tests if cleanup fails


def create_server_fixture(port: int):
    """Factory function to create a server fixture for a given port."""
    @pytest.fixture
    def server_fixture():
        kill_process_on_port(port)

        proc = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1.0)  # Wait for startup
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
