import logging
import json
from pathlib import Path
from socket import socket, AF_UNIX
import argparse

import toml

from .responses import (
    PauseResponse,
    ResumeResponse,
    StartResponse,
    StatusResponse,
    StopResponse,
)

from .commands import Command


def send_command(command):
    command = json.dumps(command).encode()
    logging.debug(f"{command=}")
    s = socket(family=AF_UNIX)
    s.connect("/tmp/pomodoro.sock")
    s.send(command)
    response = json.loads(s.recv(4096).decode("utf-8"))
    if response["response"] == "INVALID_COMMAND":
        raise RuntimeError("Error: Invalid command sent to daemon!")
    return response


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


def format_duration(duration):
    assert duration <= 99 * 3600, "Provided duration is too large to format!"
    assert duration >= 0, "Expected non-negative duration, received negative one!"
    hours = duration // 3600
    remaining = duration % 3600
    minutes = remaining // 60
    seconds = remaining % 60
    return f"{hours:{0}>2}:{minutes:{0}>2}:{seconds:{0}>2}"


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
    if duration > 99 * 3600:
        print(f"Error: Expected duration to be between 0s and 99h, got {duration}s")
        exit(1)
    response = send_command({"command": Command.START, "duration": duration})
    match response:
        case {"response": StartResponse.OK, "duration": duration}:
            print(f"Timer for {format_duration(duration)} started")
        case {"response": StartResponse.ALREADY_RUNNING}:
            print("Error: Timer is already running!")


def stop(args, config):
    match send_command({"command": Command.STOP}):
        case {"response": StopResponse.OK}:
            print("Timer stopped")
        case {"response": StopResponse.NOT_RUNNING}:
            print("Error: Timer not running!")


def pause(args, config):
    match send_command({"command": Command.PAUSE}):
        case {"response": PauseResponse.OK}:
            print("Timer paused")
        case {"response": PauseResponse.ALREADY_PAUSED}:
            print("Error: Timer is already paused!")
        case {"response": PauseResponse.NOT_RUNNING}:
            print("Error: Timer is not running!")


def resume(args, config):
    match send_command({"command": Command.RESUME}):
        case {"response": ResumeResponse.OK}:
            print("Timer resumed")
        case {"response": ResumeResponse.NOT_PAUSED}:
            print("Error: Timer is not paused!")


def status(args, config):
    match send_command({"command": Command.STATUS}):
        case {
            "response": StatusResponse.OK,
            "duration": duration,
            "remaining": remaining,
            "is_paused": is_paused,
        }:
            message = (
                f"{format_duration(remaining)} of {format_duration(duration)} left"
            )
            if is_paused:
                message += " (paused)"
            print(message)
        case {"response": StatusResponse.OK}:
            print("Not running")


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
