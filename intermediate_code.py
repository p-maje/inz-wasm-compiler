from abc import abstractmethod
from typing import List, Tuple, Dict

TAB = "  "
function_table = dict()


class Value:
    @abstractmethod
    def load(self, depth: int) -> List[str]:
        pass

    @abstractmethod
    def get_type(self) -> str:
        pass


class Const(Value):
    def __init__(self, value: int or float, var_type: str):
        self.value = value
        self.type = var_type

    def load(self, depth: int) -> List[str]:
        return [depth * TAB + f"{self.type}.const {self.value}"]

    def get_type(self) -> str:
        return self.type


class Local(Value):
    name: str
    type: str

    def __init__(self, name, var_type):
        self.name = name
        self.type = var_type

    def load(self, depth: int) -> List[str]:
        return [depth * TAB + f"local.get ${self.name}"]

    def get_type(self) -> str:
        return self.type


class ArrayValue(Local):
    array_name: str
    index: int

    def load(self, depth: int) -> List[str]:
        return []


class FunctionCall(Value):
    callee: str
    args: List[Value]

    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

    def load(self, depth: int) -> List[str]:
        return [instruction for arg in self.args for instruction in arg.load(depth)] + \
               [depth * TAB + f"call ${self.callee}"]

    def get_type(self) -> str:
        if self.callee not in function_table:
            raise Exception(f"Function {self.callee} not found")
        return function_table[self.callee].return_type


class Expression(Value):
    operands: Tuple[Value, Value]
    operation: str

    def __init__(self, operands, operation):
        self.operands = operands
        self.operation = operation

    def load(self, depth: int) -> List[str]:
        return [instruction for op in self.operands for instruction in op.load(depth)] + \
               [depth * TAB + f"{self.get_type()}.{self.operation}"]

    def get_type(self) -> str:
        if self.operands[0].get_type() != self.operands[1].get_type():
            raise Exception("Type mismatch")
        return self.operands[0].get_type()


class Command:
    @abstractmethod
    def extract(self, depth: int) -> List[str]:
        pass


class IOCommand(Command):
    operation: str
    value: Value

    def __init__(self, operation, value):
        self.operation = operation
        self.value = value

    def extract(self, depth: int) -> List[str]:
        return self.value.load(depth) + [depth * TAB + f"call $~{self.operation}_{self.value.get_type()}"]


class AssignCommand(Command):
    target: Local
    value: Value

    def __init__(self, target, value):
        self.target = target
        self.value = value

    def extract(self, depth: int) -> List[str]:
        if self.target.type != self.value.get_type():
            raise Exception("Type mismatch")
        return self.value.load(depth) + [depth * TAB + f"local.set ${self.target.name}"]


class ReturnCommand(Command):
    value: Value

    def __init__(self, value):
        self.value = value

    def extract(self, depth: int) -> List[str]:
        return self.value.load(depth)


class CallCommand(Command):
    def __init__(self, function_call: FunctionCall):
        self.call = function_call

    def extract(self, depth: int) -> List[str]:
        instructions = self.call.load(depth)
        if function_table[self.call.callee].return_type is not None:
            instructions += ['drop']
        return instructions


class Function:
    def __init__(self, name: str, args: List[Local], locals: List[Local], commands: List[Command], return_type=None):
        self.name = name
        self.args = args
        self.locals = locals
        self.commands = commands
        self.return_type = return_type

    def generate_code(self) -> List[str]:
        instructions = [f'(func ${self.name}']
        if self.args:
            instructions += [TAB + " ".join(f"(param ${var.name} {var.type})" for var in self.args)]
        if self.return_type is not None:
            instructions += [TAB + f"(result {self.return_type})"]
        if self.locals:
            instructions += [TAB + " ".join(f"(local ${var.name} {var.type})" for var in self.locals)]
        for command in self.commands:
            instructions.extend(command.extract(1))
        instructions.append(")")
        return [TAB + instruction for instruction in instructions]


class Module:
    def __init__(self, functions: List[Function]):
        self.functions = functions

    def generate_code(self) -> str:
        global function_table
        instructions = ['(module',
                        TAB + '(func $~write_i32 (import "imports" "write") (param i32))',
                        TAB + '(func $~write_f32 (import "imports" "write") (param f32))']

        function_table = {func.name: func for func in self.functions}
        for function in self.functions:
            instructions += function.generate_code()

        instructions += [TAB + '(export "main" (func $main))', ')']
        return "\n".join(instructions)
