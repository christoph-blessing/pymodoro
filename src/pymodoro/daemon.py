import logging
import os
import subprocess
import sys
import time
import toml
from multiprocessing import Pipe, Process
from pathlib import Path
from socket import AF_UNIX, socket


class AlreadyRunning(Exception):
    pass


class NotRunning(Exception):
    pass


class AlreadyPaused(Exception):
    pass


class NotPaused(Exception):
    pass


class Timer:
    def __init__(self, config):
        self._timer = None
        self._config = config

    def start(self, duration):
        if self._is_running():
            raise AlreadyRunning
        parent_conn, child_conn = Pipe()
        process = Process(target=run_timer, args=(child_conn, duration, self._config))
        process.start()
        self._timer = {"process": process, "conn": parent_conn}

    def stop(self):
        if not self._is_running():
            raise NotRunning
        assert self._timer is not None
        self._timer["conn"].send("STOP")

    def status(self):
        if not self._is_running():
            return
        assert self._timer is not None
        self._timer["conn"].send("STATUS")
        return self._timer["conn"].recv()

    def pause(self):
        if self._is_paused():
            raise AlreadyPaused
        if not self._is_running():
            raise NotRunning
        assert self._timer is not None
        self._timer["conn"].send("PAUSE")

    def resume(self):
        if not self._is_paused():
            raise NotPaused
        assert self._timer
        self._timer["conn"].send("RESUME")

    def _cleanup(self):
        if not self._timer:
            return
        if not self._timer["process"].is_alive():
            self._timer = None

    def _is_running(self):
        self._cleanup()
        return self._timer is not None

    def _is_paused(self):
        status = self.status()
        if status is None:
            return False
        return status["is_paused"]


def run_timer(conn, duration, config):
    passed = 0
    is_paused = False
    while passed < duration:
        if not is_paused:
            time.sleep(0.001)
            passed += 1
            if not conn.poll():
                continue
        match conn.recv():
            case "STATUS":
                conn.send(
                    {
                        "duration": duration,
                        "remaining": duration - passed,
                        "is_paused": is_paused,
                    }
                )
            case "STOP":
                break
            case "PAUSE":
                is_paused = True
            case "RESUME":
                is_paused = False
    else:
        subprocess.run(config["done_cmd"])
    sys.exit()


def main():
    logging.basicConfig(level=logging.INFO)

    config_path = Path.home() / ".config/pymodoro/config.toml"
    config = toml.load(config_path)["pymodorod"]
    logging.info(f"Loaded config: {config}")

    socket_path = Path("/tmp/pomodoro.sock")
    socket_path.unlink(missing_ok=True)

    s = socket(family=AF_UNIX)
    s.bind(str(socket_path))
    s.listen()
    timer = Timer(config)

    while True:
        conn, _ = s.accept()
        args = conn.recv(4096).decode("utf-8").split()
        match args:
            case ["start", duration]:
                try:
                    timer.start(int(duration) * 1000)
                except AlreadyRunning:
                    message = b"Error: Timer already running!"
                else:
                    message = b"Timer started"
            case ["stop"]:
                try:
                    timer.stop()
                except NotRunning:
                    message = b"Error: Timer not running!"
                else:
                    message = b"Timer stopped"
            case ["status"]:
                if (status := timer.status()) is not None:
                    message = f"{round(status['remaining'] / 1000)}s out of {round(status['duration'] / 1000)}s left"
                    if status["is_paused"]:
                        message += " (paused)"
                    message = message.encode()
                else:
                    message = b"Not running"
            case ["pause"]:
                try:
                    timer.pause()
                except AlreadyPaused:
                    message = b"Error: Timer is already paused!"
                except NotRunning:
                    message = b"Error: Timer is not running!"
                else:
                    message = b"Timer paused"
            case ["resume"]:
                try:
                    timer.resume()
                except NotPaused:
                    message = b"Error: Timer is not paused!"
                else:
                    message = b"Timer resumed"
            case _:
                message = b"Error: Invalid arguments!"
        conn.send(message)


if __name__ == "__main__":
    main()
