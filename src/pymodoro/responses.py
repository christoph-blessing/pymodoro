from enum import IntEnum, auto


class StartResponse(IntEnum):
    OK = auto()
    ALREADY_RUNNING = auto()


class StopResponse(IntEnum):
    OK = auto()
    NOT_RUNNING = auto()


class StatusResponse(IntEnum):
    OK = auto()


class PauseResponse(IntEnum):
    OK = auto()
    ALREADY_PAUSED = auto()
    NOT_RUNNING = auto()


class ResumeResponse(IntEnum):
    OK = auto()
    NOT_PAUSED = auto()
