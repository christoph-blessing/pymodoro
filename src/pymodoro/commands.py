from enum import IntEnum, auto


class Command(IntEnum):
    START = auto()
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    STATUS = auto()
