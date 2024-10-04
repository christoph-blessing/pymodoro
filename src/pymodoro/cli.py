import logging
import json
from pathlib import Path
from socket import socket, AF_UNIX
import argparse

import toml

from .commands import Command


def send_command(command):
    command = json.dumps(command).encode()
    logging.debug(f"{command=}")
    s = socket(family=AF_UNIX)
    s.connect("/tmp/pomodoro.sock")
    s.send(command)
    print(s.recv(4096).decode("utf-8"))


def parse_duration(spec):
    digits = []
    units = ["h", "m", "s"]
    largest = None
    total = 0
    for token in spec:
        if token.isdigit():
            digits.append(token)
        elif token in units:
            if largest and units.index(token) <= units.index(largest):
                raise ValueError(
                    f"Error: Expected unit smaller than '{largest}', got '{token}'!"
                )
            largest = token
            if not digits:
                raise ValueError(f"Error: Expected duration for unit '{token}'!")
            duration = int("".join(digits))
            digits.clear()
            if token == "h":
                duration *= 3600
            elif token == "m":
                duration *= 60
            total += duration
        else:
            raise ValueError(
                f"Error: Expected unit to be one of {units}, got '{token}'!"
            )
    if digits:
        raise ValueError(f"Error: Expected unit for duration '{''.join(digits)}'!")
    return total


def start(args, config):
    if args.duration_spec is None:
        duration_spec = config["default_duration"]
    else:
        duration_spec = args.duration_spec
    try:
        duration = parse_duration(duration_spec)
    except ValueError as error:
        print(error)
        exit(1)
    send_command({"command": Command.START, "duration": duration})


def stop(args, config):
    send_command({"command": Command.STOP})


def pause(args, config):
    send_command({"command": Command.PAUSE})


def resume(args, config):
    send_command({"command": Command.RESUME})


def status(args, config):
    send_command({"command": Command.STATUS})


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=Path().home() / ".config/pymodoro/config.toml",
        dest="config_path",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.set_defaults(func=status)
    subparsers = parser.add_subparsers()

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("-d", "--duration", dest="duration_spec")
    start_parser.set_defaults(func=start)

    stop_parser = subparsers.add_parser("stop")
    stop_parser.set_defaults(func=stop)

    pause_parser = subparsers.add_parser("pause")
    pause_parser.set_defaults(func=pause)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.set_defaults(func=resume)

    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(func=status)

    args = parser.parse_args()

    config = toml.load(args.config_path)["pymodoro"]

    logging.basicConfig(level=getattr(logging, args.log_level))
    logging.debug(f"{args=}")
    logging.debug(f"{config=}")

    args.func(args, config)


if __name__ == "__main__":
    main()
