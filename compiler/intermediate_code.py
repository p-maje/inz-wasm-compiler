from abc import abstractmethod
from typing import List, Tuple, Optional, Dict

from compiler.common import CompilerException

TAB = "  "
function_table = dict()
current_function: 'Function'
local_vars = dict()
arrays: Dict[str, 'Array'] = dict()
iterators = set()
active_iterators = set()
active_loops = 0


class Array:
    def __init__(self, lineno: int, name: str, array_type: str, size: int):
        self.lineno = lineno
        self.name = name
        self.type = array_type
        self.size = size
        self.start_pointer = 0

    def prepare(self):
        global arrays
        if self.name in arrays:
            raise CompilerException(f"{self.lineno}: Repeated declaration of array '{self.name}'")
        self.start_pointer = sum(arr.size for arr in arrays.values()) * 4
        arrays[self.name] = self

    def load_address_at(self, depth: int, lineno: int, index: 'Value'):
        if not index.get_type() == "i32":
            raise CompilerException(f"{lineno}: Index must be an integer")
        if isinstance(index, Const):
            return Const(index.value * 4 + self.start_pointer, "i32").load(depth)
        instructions = ["i32.const 4", "i32.mul"]
        if self.start_pointer:
            instructions += [f"i32.const {self.start_pointer}", "i32.add"]
        return index.load(depth) + [depth * TAB + instruction for instruction in instructions]


class Value:
    @abstractmethod
    def load(self, depth: int) -> List[str]:
        return []

    @abstractmethod
    def get_type(self) -> str:
        pass

    def get_local(self) -> 'Value':
        return self


class Const(Value):
    def __init__(self, value: int or float, var_type: str):
        self.value = value
        self.type = var_type

    def load(self, depth: int) -> List[str]:
        return [depth * TAB + f"{self.type}.const {self.value}"]

    def get_type(self) -> str:
        return self.type


class Local(Value):
    def __init__(self, lineno: int, name: str, var_type=None):
        self.lineno = lineno
        self.name = name
        self.type = var_type
        self.initialized = False

    def load(self, depth: int) -> List[str]:
        if not self.initialized and self.name in local_vars:
            self.initialized = local_vars[self.name].initialized
            if not self.initialized:
                raise CompilerException(f"{self.lineno}: Variable '{self.name}' not initialized")
        return [depth * TAB + f"local.get ${self.name}"]

    def get_type(self) -> str:
        if self.type:
            return self.type
        if self.name in active_iterators:
            self.type = "i32"
        else:
            if self.name not in local_vars:
                raise CompilerException(f"{self.lineno}: Variable '{self.name}' not declared")
            self.type = local_vars[self.name].type
        return self.type

    def store(self, depth: int, value: Value) -> List[str]:
        if self.name in local_vars:
            local_vars[self.name].initialized = True
        return value.load(depth) + [depth * TAB + f"local.set ${self.name}"]


class ArrayValue(Local):
    def __init__(self, lineno: int, array_name: str, index: Value):
        super().__init__(lineno, array_name)
        self.lineno = lineno
        self.name = array_name
        self.index = index
        self.array = None

    def load(self, depth: int) -> List[str]:
        self._check_arrays_existence()
        return self.array.load_address_at(depth, self.lineno, self.index) + [depth * TAB + f"{self.array.type}.load"]

    def get_type(self) -> str:
        self._check_arrays_existence()
        return self.array.type

    def store(self, depth: int, value: Value) -> List[str]:
        return self.array.load_address_at(depth, self.lineno, self.index) + value.load(depth) + \
               [depth * TAB + f"{self.array.type}.store"]

    def _check_arrays_existence(self):
        if not self.array:
            self.array = arrays.get(self.name)
            if not self.array:
                raise CompilerException(f"{self.lineno}: Array '{self.name}' not declared")


class FunctionCall(Value):
    def __init__(self, lineno: int, callee: str, args: List[Value]):
        self.lineno = lineno
        self.callee = callee
        self.args = args

    def load(self, depth: int) -> List[str]:
        function = function_table.get(self.callee)
        if not function:
            raise CompilerException(f"{self.lineno}: Function '{self.callee}' not found")
        if len(function.args) != len(self.args):
            raise CompilerException(f"{self.lineno}: Function {self.callee} expected {len(function.args)} arguments, "
                                    f"got {len(self.args)}")
        for arg, expected in zip(self.args, function.args):
            if arg.get_type() != expected.get_type():
                raise CompilerException(f"{self.lineno}: Argument {expected.name} is of type {expected.get_type()}, "
                                        f"got {arg.get_type()}")
        return [instruction for arg in self.args for instruction in arg.load(depth)] + \
               [depth * TAB + f"call ${self.callee}"]

    def get_type(self) -> str:
        if self.callee not in function_table:
            raise CompilerException(f"{self.lineno}: Function '{self.callee}' not found")
        return function_table[self.callee].return_type


class Expression(Value):
    def __init__(self, lineno: int, operands: Tuple[Value, Value], operation: str):
        self.lineno = lineno
        self.operands = operands
        self.operation = operation

    def load(self, depth: int) -> List[str]:
        return [instruction for op in self.operands for instruction in op.load(depth)] + \
               [depth * TAB + f"{self.get_type()}.{self.operation}"]

    def get_type(self) -> str:
        if self.operands[0].get_type() != self.operands[1].get_type():
            raise CompilerException(f"{self.lineno}: Type mismatch")
        expr_type = self.operands[0].get_type()
        if expr_type == "f32" and self.operation.endswith("_s"):
            self.operation = self.operation[:-2]
            if self.operation == "rem":
                raise CompilerException(f"{self.lineno}: Operation '%' is not defined for float values")
        return expr_type


class Command:
    @abstractmethod
    def extract(self, depth: int) -> List[str]:
        pass


class WriteCommand(Command):
    value: Value

    def __init__(self, lineno, value):
        self.lineno = lineno
        self.value = value

    def extract(self, depth: int) -> List[str]:
        val_type = self.value.get_type()
        if not val_type:
            raise CompilerException(f"{self.lineno}: Expression has no value")
        return self.value.load(depth) + [depth * TAB + f"call $~write_{val_type}"]


class ReadCommand(Command):
    target: Local

    def __init__(self, lineno, target):
        self.lineno = lineno
        self.target = target

    def extract(self, depth: int) -> List[str]:
        val_type = self.target.get_type()
        if self.target.name in active_iterators:
            raise CompilerException(f"{self.lineno}: Assigning to an iterator")
        if self.target.name in local_vars:
            local_vars[self.target.name].initialized = True
        read_call = FunctionCall(self.lineno, f"~read_{val_type}", [])
        read_call.load = lambda d: [TAB * d + f"call $~read_{val_type}"]
        return self.target.store(depth, read_call)


class AssignCommand(Command):
    target: Local
    value: Value

    def __init__(self, lineno, target, value, loop_operation=False):
        self.lineno = lineno
        self.target = target
        self.value = value
        self.loop_operation = loop_operation

    def extract(self, depth: int) -> List[str]:
        if self.target.get_type() != self.value.get_type():
            raise CompilerException(f"{self.lineno}: Type mismatch")
        if not self.loop_operation and self.target.name in active_iterators:
            raise CompilerException(f"{self.lineno}: Assigning to an iterator")
        return self.target.store(depth, self.value)


class ReturnCommand(Command):
    value: Optional[Value]

    def __init__(self, lineno, value):
        self.lineno = lineno
        self.value = value

    def extract(self, depth: int) -> List[str]:
        value_type = self.value.get_type() if self.value else None
        if current_function.return_type != value_type:
            raise CompilerException(f"{self.lineno}: Return type of function '{current_function.name}' should be "
                                    f"{current_function.return_type}, is {self.value.get_type()}")
        instructions = self.value.load(depth) if self.value else []
        return instructions + [depth * TAB + f"return"]


class CallCommand(Command):
    def __init__(self, function_call: FunctionCall):
        self.call = function_call

    def extract(self, depth: int) -> List[str]:
        instructions = self.call.load(depth)
        if function_table[self.call.callee].return_type is not None:
            instructions += [depth * TAB + 'drop']
        return instructions


class IfCommand(Command):
    def __init__(self, condition: Expression, commands_if: List[Command], commands_else: List[Command]):
        self.condition = condition
        self.commands_if = commands_if
        self.commands_else = commands_else

    def extract(self, depth: int) -> List[str]:
        instructions = self.condition.load(depth)
        instructions += [depth * TAB + "if"]
        for command in self.commands_if:
            instructions += command.extract(depth + 1)
        if self.commands_else:
            instructions += [depth * TAB + "else"]
            for command in self.commands_else:
                instructions += command.extract(depth + 1)
        instructions += [depth * TAB + "end"]
        return instructions


class WhileLoop(Command):
    def __init__(self, lineno: int, condition: Expression, commands: List[Command]):
        self.lineno = lineno
        self.condition = self._invert_condition(condition)
        self.commands = commands

    @staticmethod
    def _invert_condition(condition):
        inverses = {
            "le_s": "gt_s",
            "lt_s": "ge_s",
            "ge_s": "lt_s",
            "gt_s": "le_s",
            "eq": "ne",
            "ne": "eq",
        }
        condition.operation = inverses[condition.operation]
        return condition

    def extract(self, depth: int) -> List[str]:
        global active_loops
        active_loops += 1
        loop_name = f"$~while{active_loops}"
        instructions = [depth * TAB + f"(loop {loop_name} (block {loop_name}~block"]
        instructions += self.condition.load(depth + 1)
        instructions += [(depth + 1) * TAB + f"br_if {loop_name}~block"]
        for command in self.commands:
            instructions += command.extract(depth + 1)
        instructions += [(depth + 1) * TAB + f"br {loop_name}", depth * TAB + f"))"]
        active_loops -= 1
        return instructions


class ForLoop(Command):
    def __init__(self, lineno: int, iterator: str, start: Value, stop: Value, direction: str, commands: List[Command]):
        self.lineno = lineno
        self.iterator_name = iterator
        self.start = start
        self.stop = stop
        self.direction = direction
        self.commands = commands

    def extract(self, depth: int) -> List[str]:
        global active_iterators
        if self.iterator_name in local_vars:
            raise CompilerException(f"{self.lineno}: Iterator shadows a local variable '{self.iterator_name}'")
        if self.iterator_name in active_iterators:
            raise CompilerException(f"{self.lineno}: Iterator shadows a previous iterator '{self.iterator_name}'")
        iterators.add(self.iterator_name)
        active_iterators.add(self.iterator_name)
        iterator = Local(self.lineno, self.iterator_name, "i32")
        instructions = AssignCommand(self.lineno, iterator, self.start, loop_operation=True).extract(depth)

        loop_name = f"$~{self.iterator_name}"
        instructions += [depth * TAB + f"(loop {loop_name} (block {loop_name}~block"]
        instructions += Expression(
            self.lineno, (iterator, self.stop), "gt_s" if self.direction == "up" else "lt_s").load(depth + 1)
        instructions += [(depth + 1) * TAB + f"br_if {loop_name}~block"]
        for command in self.commands:
            instructions += command.extract(depth + 1)

        iterator_update = Expression(self.lineno, (iterator, Const(1, "i32")),
                                     "add" if self.direction == "up" else "sub")
        instructions += AssignCommand(self.lineno, iterator, iterator_update, loop_operation=True).extract(depth + 1)

        instructions += [(depth + 1) * TAB + f"br {loop_name}", depth * TAB + f"))"]
        active_iterators.remove(self.iterator_name)
        return instructions


class Function:
    def __init__(self, lineno: int, name: str, args: List[Local], locals: List[Local], commands: List[Command],
                 return_type=None):
        self.lineno = lineno
        self.name = name
        self.args = args
        self.locals = locals
        self.commands = commands
        self.return_type = return_type

    def _check_number_of_declarations(self, declarations: List[Local]):
        declared = set(local_vars.keys())
        for var in declarations:
            if var.name in declared:
                raise CompilerException(f"{self.lineno}: Redeclaration of '{var.name}'")
            declared.add(var.name)
        return declared

    def generate_code(self) -> List[str]:
        global current_function, local_vars, iterators, active_iterators
        current_function = self
        local_vars.clear()
        iterators.clear()
        active_iterators.clear()
        header = [f'(func ${self.name}']
        if self.args:
            self._check_number_of_declarations(self.args)
            header += [
                TAB + " ".join(f"(param ${var.name} {var.type})" for var in self.args if not isinstance(var, Array))]
            for var in self.args:
                var.initialized = True
            local_vars.update({var.name: var for var in self.args})
        if self.return_type is not None:
            header += [TAB + f"(result {self.return_type})"]
        if self.locals:
            self._check_number_of_declarations(self.locals)
            header += [
                TAB + " ".join(f"(local ${var.name} {var.type})" for var in self.locals if not isinstance(var, Array))]
            local_vars.update({var.name: var for var in self.locals})
        instructions = []
        for command in self.commands:
            instructions.extend(command.extract(1))
            if isinstance(command, ReturnCommand):
                break
        else:
            if self.return_type:
                raise CompilerException(f"{self.lineno}: Function needs to end with an explicit return statement")
        if iterators:
            header += [TAB + " ".join(f"(local ${var} i32)" for var in iterators)]
        instructions = header + instructions
        instructions.append(")")
        return [TAB + instruction for instruction in instructions]


class Module:
    def __init__(self, array_declarations: List[Array], functions: List[Function]):
        self.arrays = array_declarations
        self.functions = functions

    def generate_code(self) -> str:
        global function_table, arrays
        instructions = ['(module',
                        TAB + '(func $~write_i32 (import "imports" "write") (param i32))',
                        TAB + '(func $~read_i32 (import "imports" "readInt") (result i32))',
                        TAB + '(func $~write_f32 (import "imports" "write") (param f32))',
                        TAB + '(func $~read_f32 (import "imports" "readFloat") (result f32))',
                        TAB + '(memory 1)']

        arrays = dict()
        for array in self.arrays:
            array.prepare()
        function_table = {func.name: func for func in self.functions}
        for function in self.functions:
            instructions += function.generate_code()

        instructions += [TAB + '(export "main" (func $main))', ')']
        return "\n".join(instructions)
