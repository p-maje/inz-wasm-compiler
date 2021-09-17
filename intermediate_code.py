from abc import abstractmethod
from typing import List, Tuple


class Value:
    type: str

    @abstractmethod
    def load(self) -> str:
        pass


class Const(Value):
    value: int or float

    def __init__(self, value, var_type):
        self.value = value
        self.type = var_type

    def load(self) -> str:
        return f"{self.type}.const {self.value}"


class Local(Value):
    name: str

    def __init__(self, name, var_type):
        self.name = name
        self.type = var_type

    def load(self) -> str:
        return f"local.get ${self.name}"


class ArrayValue(Local):
    array_name: str
    index: int

    def load(self) -> str:
        return ""


class Expression(Value):
    operands: Tuple[Value, Value]
    operation: str

    def __init__(self, operands, operation):
        self.operands = operands
        self.operation = operation
        if operands[0].type != operands[1].type:
            raise Exception("Type mismatch")
        self.type = operands[0].type

    def load(self) -> str:
        value = "\n".join(f"{op.load()}" for op in self.operands)
        return value + "\n" + f"{self.type}.{self.operation}"


class Command:
    @abstractmethod
    def extract(self) -> str:
        pass


class IOCommand(Command):
    operation: str
    value: Value

    def __init__(self, operation, value):
        self.operation = operation
        self.value = value

    def extract(self) -> str:
        return "\n".join([self.value.load(), f"call $~{self.operation}_{self.value.type}"])


class AssignCommand(Command):
    target: Local
    value: Value

    def __init__(self, target, value):
        self.target = target
        self.value = value
        if target.type != value.type:
            raise Exception("Type mismatch")

    def extract(self) -> str:
        return "\n".join([self.value.load(), f"local.set ${self.target.name}"])


class CallCommand(Command):
    callee: str
    args: List[Value]

    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

    def extract(self) -> str:
        instructions = [arg.load() for arg in self.args] + [f"call ${self.callee}"]
        return "\n".join(instructions)

