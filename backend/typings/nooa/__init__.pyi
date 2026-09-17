from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

class Agent:
    def __init__(self, llm: Any = ...) -> None: ...

class PredictStrategy:
    def __init__(self, config: Any = ...) -> None: ...

def strategy(value: PredictStrategy) -> Callable[[F], F]: ...
