from abc import abstractmethod

from compiler.common import CompilerException

TAB = "  "
NUMBER_MEMSIZE = 4  # in bytes, so int32 and float32


class GlobalContext:
    def __init__(self, functions: list["Function"], arrays: list["Array"]):
        self.function_table: dict[str, "Function"] = {function.name: function for function in functions}
        self.arrays: dict[str, "Array"] = self._prepare_array_declarations(arrays)

    @staticmethod
    def _prepare_array_declarations(arrays: list["Array"]) -> dict[str, "Array"]:
        declared_arrays = {}
        for array in arrays:
            if array.name in declared_arrays:
                raise CompilerException(
                    f"{array.lineno}: Repeated declaration of array '{array.name}'"
                )
            array.start_pointer = sum(arr.size for arr in declared_arrays.values()) * NUMBER_MEMSIZE
            declared_arrays[array.name] = array
        return declared_arrays


class LocalContext:
    def __init__(self, global_context: GlobalContext, current_function: "Function"):
        self.global_context = global_context
        self.current_function = current_function
        self.local_vars: dict[str, "Local"] = {}
        self.iterators: set[str] = set()
        self.active_iterators: set[str] = set()
        self.active_loop_count = 0


class Array:
    def __init__(self, lineno: int, name: str, array_type: str, size: int):
        self.lineno = lineno
        self.name = name
        self.type = array_type
        self.size = size
        self.start_pointer = 0

    def load_address_at(self, context: LocalContext, depth: int, lineno: int, index: "Value"):
        if not index.get_type(context) == "i32":
            raise CompilerException(f"{lineno}: Index must be an integer")
        if isinstance(index, Const):
            return Const(index.value * 4 + self.start_pointer, "i32").load(context, depth)
        instructions = ["i32.const 4", "i32.mul"]
        if self.start_pointer:
            instructions += [f"i32.const {self.start_pointer}", "i32.add"]
        return index.load(context, depth) + [
            depth * TAB + instruction for instruction in instructions
        ]


class Value:
    @abstractmethod
    def load(self, context: LocalContext, depth: int) -> list[str]:
        return []

    @abstractmethod
    def get_type(self, context: LocalContext) -> str:
        pass

    def get_local(self) -> "Value":
        return self


class Const(Value):
    def __init__(self, value: int or float, var_type: str):
        self.value = value
        self.type = var_type

    def load(self, context: LocalContext, depth: int) -> list[str]:
        return [depth * TAB + f"{self.type}.const {self.value}"]

    def get_type(self, context: LocalContext) -> str:
        return self.type


class Local(Value):
    def __init__(self, lineno: int, name: str, var_type=None):
        self.lineno = lineno
        self.name = name
        self.type = var_type
        self.initialized = False

    def load(self, context: LocalContext, depth: int) -> list[str]:
        if not self.initialized and self.name in context.local_vars:
            self.initialized = context.local_vars[self.name].initialized
            if not self.initialized:
                raise CompilerException(
                    f"{self.lineno}: Variable '{self.name}' not initialized"
                )
        return [depth * TAB + f"local.get ${self.name}"]

    def get_type(self, context: LocalContext) -> str:
        if self.type:
            return self.type
        if self.name in context.active_iterators:
            self.type = "i32"
        else:
            if self.name not in context.local_vars:
                raise CompilerException(
                    f"{self.lineno}: Variable '{self.name}' not declared"
                )
            self.type = context.local_vars[self.name].type
        return self.type

    def store(self, context: LocalContext, depth: int, value: Value) -> list[str]:
        if self.name in context.local_vars:
            context.local_vars[self.name].initialized = True
        return value.load(context, depth=depth) + [depth * TAB + f"local.set ${self.name}"]


class ArrayValue(Local):
    def __init__(self, lineno: int, array_name: str, index: Value):
        super().__init__(lineno, array_name)
        self.lineno = lineno
        self.name = array_name
        self.index = index
        self.array = None

    def load(self, context: LocalContext, depth: int) -> list[str]:
        self._check_arrays_existence(context)
        return self.array.load_address_at(context, depth, self.lineno, self.index) + [
            depth * TAB + f"{self.array.type}.load"
        ]

    def get_type(self, context: LocalContext) -> str:
        self._check_arrays_existence(context)
        return self.array.type

    def store(self, context: LocalContext, depth: int, value: Value) -> list[str]:
        return (
            self.array.load_address_at(context, depth, self.lineno, self.index)
            + value.load(context, depth)
            + [depth * TAB + f"{self.array.type}.store"]
        )

    def _check_arrays_existence(self, context: LocalContext):
        if not self.array:
            self.array = context.global_context.arrays.get(self.name)
            if not self.array:
                raise CompilerException(
                    f"{self.lineno}: Array '{self.name}' not declared"
                )


class FunctionCall(Value):
    def __init__(self, lineno: int, callee: str, args: list[Value]):
        self.lineno = lineno
        self.callee = callee
        self.args = args

    def load(self, context: LocalContext, depth: int) -> list[str]:
        function = context.global_context.function_table.get(self.callee)
        if not function:
            raise CompilerException(
                f"{self.lineno}: Function '{self.callee}' not found"
            )
        if len(function.args) != len(self.args):
            raise CompilerException(
                f"{self.lineno}: Function {self.callee} expected {len(function.args)} arguments, "
                f"got {len(self.args)}"
            )
        for arg, expected in zip(self.args, function.args):
            if arg.get_type(context) != expected.get_type(context):
                raise CompilerException(
                    f"{self.lineno}: Argument {expected.name} is of type {expected.get_type(context)}, "
                    f"got {arg.get_type(context)}"
                )
        return [instruction for arg in self.args for instruction in arg.load(context, depth)] + [
            depth * TAB + f"call ${self.callee}"
        ]

    def get_type(self, context: LocalContext) -> str:
        callee_function = context.global_context.function_table.get(self.callee)
        if not self.callee:
            raise CompilerException(
                f"{self.lineno}: Function '{self.callee}' not found"  # TODO this check is duplicated, annoying
            )
        return callee_function.return_type


class Expression(Value):
    def __init__(self, lineno: int, operands: tuple[Value, Value], operation: str):
        self.lineno = lineno
        self.operands = operands
        self.operation = operation

    def load(self, context: LocalContext, depth: int) -> list[str]:
        return [
            instruction for op in self.operands for instruction in op.load(context, depth)
        ] + [depth * TAB + f"{self.get_type(context)}.{self.operation}"]

    def get_type(self, context: LocalContext) -> str:
        if self.operands[0].get_type(context) != self.operands[1].get_type(context):
            raise CompilerException(f"{self.lineno}: Type mismatch")
        expr_type = self.operands[0].get_type(context)
        if expr_type == "f32" and self.operation.endswith("_s"):
            self.operation = self.operation[:-2]
            if self.operation == "rem":
                raise CompilerException(
                    f"{self.lineno}: Operation '%' is not defined for float values"
                )
        return expr_type


class Command:
    @abstractmethod
    def extract(self, context: LocalContext, depth: int) -> list[str]:
        ...


class WriteCommand(Command):
    def __init__(self, lineno: int, value: Value):
        self.lineno = lineno
        self.value = value

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        val_type = self.value.get_type(context)
        if not val_type:
            raise CompilerException(f"{self.lineno}: Expression has no value")
        return self.value.load(context, depth) + [depth * TAB + f"call $~write_{val_type}"]


class ReadCommand(Command):
    def __init__(self, lineno: int, target: Local):
        self.lineno = lineno
        self.target = target

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        val_type = self.target.get_type(context)
        if self.target.name in context.active_iterators:
            raise CompilerException(f"{self.lineno}: Assigning to an iterator")
        if self.target.name in context.local_vars:
            context.local_vars[self.target.name].initialized = True
        read_call = FunctionCall(self.lineno, f"~read_{val_type}", [])
        read_call.load = lambda d: [TAB * d + f"call $~read_{val_type}"]
        return self.target.store(context, depth, read_call)


class AssignCommand(Command):
    def __init__(self, lineno: int, target: Local, value: Value, loop_operation: bool = False):
        self.lineno = lineno
        self.target = target
        self.value = value
        self.loop_operation = loop_operation

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        if self.target.get_type(context) != self.value.get_type(context):
            raise CompilerException(f"{self.lineno}: Type mismatch")
        if not self.loop_operation and self.target.name in context.active_iterators:
            raise CompilerException(f"{self.lineno}: Assigning to an iterator")
        return self.target.store(context, depth, self.value)


class ReturnCommand(Command):
    def __init__(self, lineno: int, value: Value | None):
        self.lineno = lineno
        self.value = value

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        value_type = self.value.get_type(context) if self.value else None
        if context.current_function.return_type != value_type:
            raise CompilerException(
                f"{self.lineno}: Return type of function '{context.current_function.name}' should be "
                f"{context.current_function.return_type}, is {self.value.get_type(context)}"
            )
        instructions = self.value.load(context, depth) if self.value else []
        return instructions + [depth * TAB + f"return"]


class CallCommand(Command):
    def __init__(self, function_call: FunctionCall):
        self.call = function_call

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        instructions = self.call.load(context, depth)
        function = context.global_context.function_table[self.call.callee]
        if function.return_type is not None:
            instructions += [depth * TAB + "drop"]
        return instructions


class IfCommand(Command):
    def __init__(
        self,
        condition: Expression,
        commands_if: list[Command],
        commands_else: list[Command],
    ):
        self.condition = condition
        self.commands_if = commands_if
        self.commands_else = commands_else

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        instructions = self.condition.load(context, depth)
        instructions += [depth * TAB + "if"]
        for command in self.commands_if:
            instructions += command.extract(context, depth=depth+1)
        if self.commands_else:
            instructions += [depth * TAB + "else"]
            for command in self.commands_else:
                instructions += command.extract(context, depth=depth+1)
        instructions += [depth * TAB + "end"]
        return instructions


class WhileLoop(Command):
    def __init__(self, lineno: int, condition: Expression, commands: list[Command]):
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

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        context.active_loop_count += 1
        loop_name = f"$~while{context.active_loop_count}"
        instructions = [depth * TAB + f"(loop {loop_name} (block {loop_name}~block"]
        instructions += self.condition.load(depth + 1)
        instructions += [(depth + 1) * TAB + f"br_if {loop_name}~block"]
        for command in self.commands:
            instructions += command.extract(context, depth=depth+1)
        instructions += [(depth + 1) * TAB + f"br {loop_name}", depth * TAB + f"))"]
        context.active_loop_count -= 1
        return instructions


class ForLoop(Command):
    def __init__(
        self,
        lineno: int,
        iterator: str,
        start: Value,
        stop: Value,
        direction: str,
        commands: list[Command],
    ):
        self.lineno = lineno
        self.iterator_name = iterator
        self.start = start
        self.stop = stop
        self.direction = direction
        self.commands = commands

    def extract(self, context: LocalContext, depth: int) -> list[str]:
        if self.iterator_name in context.local_vars:
            raise CompilerException(
                f"{self.lineno}: Iterator shadows a local variable '{self.iterator_name}'"
            )
        if self.iterator_name in context.active_iterators:
            raise CompilerException(
                f"{self.lineno}: Iterator shadows a previous iterator '{self.iterator_name}'"
            )
        context.iterators.add(self.iterator_name)
        context.active_iterators.add(self.iterator_name)
        iterator = Local(self.lineno, self.iterator_name, "i32")
        instructions = AssignCommand(
            self.lineno, iterator, self.start, loop_operation=True
        ).extract(context, depth=depth)

        loop_name = f"$~{self.iterator_name}"
        instructions += [depth * TAB + f"(loop {loop_name} (block {loop_name}~block"]
        instructions += Expression(
            self.lineno,
            (iterator, self.stop),
            "gt_s" if self.direction == "up" else "lt_s",
        ).load(context, depth=depth+1)
        instructions += [(depth + 1) * TAB + f"br_if {loop_name}~block"]
        for command in self.commands:
            instructions += command.extract(context, depth=depth+1)

        iterator_update = Expression(
            self.lineno,
            (iterator, Const(1, "i32")),
            "add" if self.direction == "up" else "sub",
        )
        instructions += AssignCommand(
            self.lineno, iterator, iterator_update, loop_operation=True
        ).extract(context, depth=depth+1)

        instructions += [(depth + 1) * TAB + f"br {loop_name}", depth * TAB + f"))"]
        context.active_iterators.remove(self.iterator_name)
        return instructions


class Function:
    def __init__(
        self,
        lineno: int,
        name: str,
        args: list[Local],
        local_declarations: list[Local],
        commands: list[Command],
        return_type=None,
    ):
        self.lineno = lineno
        self.name = name
        self.args = args
        self.local_declarations = local_declarations
        self.commands = commands
        self.return_type = return_type

    def _check_number_of_declarations(self, declarations: list[Local], context: LocalContext):
        for var in declarations:
            if var.name in context.local_vars:
                raise CompilerException(f"{self.lineno}: Redeclaration of '{var.name}'")
            context.local_vars[var.name] = var

    def generate_code(self, global_context: GlobalContext) -> list[str]:
        context = LocalContext(global_context, self)
        header = [f"(func ${self.name}"]
        if self.args:
            self._check_number_of_declarations(self.args, context)
            header += [
                TAB
                + " ".join(
                    f"(param ${var.name} {var.type})"
                    for var in self.args
                    if not isinstance(var, Array)
                )
            ]
            for var in self.args:
                var.initialized = True
        if self.return_type is not None:
            header += [TAB + f"(result {self.return_type})"]
        if self.local_declarations:
            self._check_number_of_declarations(self.local_declarations, context)
            header += [
                TAB
                + " ".join(
                    f"(local ${var.name} {var.type})"
                    for var in self.local_declarations
                    if not isinstance(var, Array)
                )
            ]
        instructions = []
        for command in self.commands:
            instructions.extend(command.extract(context, depth=1))
            if isinstance(command, ReturnCommand):
                break
        else:
            if self.return_type:
                raise CompilerException(
                    f"{self.lineno}: Function needs to end with an explicit return statement"
                )
        if context.iterators:
            header += [TAB + " ".join(f"(local ${var} i32)" for var in context.iterators)]
        instructions = header + instructions
        instructions.append(")")
        return [TAB + instruction for instruction in instructions]


class Module:
    def __init__(self, array_declarations: list[Array], functions: list[Function]):
        self.arrays = array_declarations
        self.functions = functions

    def generate_code(self) -> str:
        context = GlobalContext(self.functions, self.arrays)
        instructions = [
            "(module",
            TAB + '(func $~write_i32 (import "imports" "write") (param i32))',
            TAB + '(func $~read_i32 (import "imports" "readInt") (result i32))',
            TAB + '(func $~write_f32 (import "imports" "write") (param f32))',
            TAB + '(func $~read_f32 (import "imports" "readFloat") (result f32))',
            TAB + "(memory 1)",
        ]
        for function in self.functions:
            instructions += function.generate_code(context)
        instructions += [TAB + '(export "main" (func $main))', ")"]
        return "\n".join(instructions)
