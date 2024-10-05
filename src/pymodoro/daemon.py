import argparse
import json
import logging
import subprocess
import sys
import time
import toml
from multiprocessing import Pipe, Process
from pathlib import Path
from socket import AF_UNIX, socket

from pymodoro.commands import Command
from pymodoro.responses import (
    PauseResponse,
    ResumeResponse,
    StartResponse,
    StatusResponse,
    StopResponse,
)


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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=Path().home() / ".config/pymodoro/config.toml",
        dest="config_path",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    command = parser.parse_args()

    config = toml.load(command.config_path)["pymodorod"]

    logging.basicConfig(level=getattr(logging, command.log_level))
    logging.debug(f"{command=}")
    logging.debug(f"{config=}")

    socket_path = Path("/tmp/pomodoro.sock")
    socket_path.unlink(missing_ok=True)

    s = socket(family=AF_UNIX)
    s.bind(str(socket_path))
    s.listen()
    timer = Timer(config)

    while True:
        conn, _ = s.accept()
        command = json.loads(conn.recv(4096).decode("utf-8"))
        logging.debug(f"{command=}")
        match command:
            case {"command": Command.START, "duration": duration}:
                try:
                    timer.start(int(duration) * 1000)
                except AlreadyRunning:
                    response = {"response": StartResponse.ALREADY_RUNNING}
                else:
                    response = {"response": StartResponse.OK, "duration": duration}
            case {"command": Command.STOP}:
                try:
                    timer.stop()
                except NotRunning:
                    response = {"response": StopResponse.NOT_RUNNING}
                else:
                    response = {"response": StopResponse.OK}
            case {"command": Command.STATUS}:
                if (status := timer.status()) is not None:
                    response = {
                        "response": StatusResponse.OK,
                        "duration": status["duration"] // 1000,
                        "remaining": status["remaining"] // 1000,
                        "is_paused": status["is_paused"],
                    }
                else:
                    response = {"response": StatusResponse.OK}
            case {"command": Command.PAUSE}:
                try:
                    timer.pause()
                except AlreadyPaused:
                    response = {"response": PauseResponse.ALREADY_PAUSED}
                except NotRunning:
                    response = {"response": PauseResponse.NOT_RUNNING}
                else:
                    response = {"response": PauseResponse.OK}
            case {"command": Command.RESUME}:
                try:
                    timer.resume()
                except NotPaused:
                    response = {"response": ResumeResponse.NOT_PAUSED}
                else:
                    response = {"response": ResumeResponse.OK}
            case _:
                response = {"response": "INVALID_COMMAND"}
        response = json.dumps(response).encode()
        logging.debug(f"{response=}")
        conn.send(response)


if __name__ == "__main__":
    main()
