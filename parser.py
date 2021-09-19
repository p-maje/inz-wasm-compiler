from sly import Lexer, Parser

from intermediate_code import Local, Const, IOCommand, AssignCommand, Expression, CallCommand, ReturnCommand, Function, \
    Module, FunctionCall, IfCommand


class ImpLexer(Lexer):
    # @_(r'\[[^\]]*\]')
    # def ignore_comment(self, t):
    #     self.lineno += t.value.count('\n')

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)

    tokens = {DEF, WITH, MAIN, BEGIN, END, PID, NUM_FLOAT, NUM_INT, IF, ELSE, WHILE, FOR, FROM, TO,
              DOWNTO, READ, WRITE, RETURN, EQ, NEQ, GT, LT, GEQ, LEQ, GETS, INT, FLOAT}

    DEF = r"def"
    WITH = r"with"
    BEGIN = r"{"
    INT = r"int"
    FLOAT = r"float"

    END = r"}"

    WHILE = r"while"
    FOR = r"for"
    IF = r"if"
    ELSE = r"else"

    DOWNTO = r"downto"
    TO = r"to"

    FROM = r"from"

    READ = r"read"
    WRITE = r"write"
    RETURN = r"return"

    NEQ = r"!="
    GEQ = r">="
    LEQ = r"<="
    EQ = r"=="
    GT = r">"
    LT = r"<"
    GETS = r"="
    MAIN = r"main"

    PID = r"[_a-z]+"

    @_(r'\d+\.\d+')
    def NUM_FLOAT(self, t):
        t.value = float(t.value)
        return t

    @_(r'\d+')
    def NUM_INT(self, t):
        t.value = int(t.value)
        return t

    def error(self, t):
        raise Exception(f"{t.lineno}: Illegal character '{t.value[0]}'")

    literals = {'+', '-', '*', '/', '%', ',', ';', '[', ']', '(', ')'}
    ignore = ' \t'


class ImpParser(Parser):
    tokens = ImpLexer.tokens

    def __init__(self):
        self.locals = dict()
        self.local_arrays = dict()
        self.code = None

    @_('procedures main')
    def program(self, p):
        return Module(p.procedures + [p.main])

    @_('')
    def procedures(self, p):
        return []

    @_('procedures procedure')
    def procedures(self, p):
        return p[0] + [p[1]]

    @_('DEF PID args declarations BEGIN commands END')
    def procedure(self, p):
        return Function(p.PID, p.args, p.declarations, p.commands)

    @_('type PID args declarations BEGIN commands END')
    def procedure(self, p):
        return Function(p.PID, p.args, p.declarations, p.commands, p.type)

    @_('DEF MAIN "(" ")" declarations BEGIN commands END')
    def main(self, p):
        return Function("main", [], p.declarations, p.commands)

    @_('')
    def declarations(self, p):
        return []

    @_('WITH nonempty_args')
    def declarations(self, p):
        return p[1]

    @_('"(" ")"')
    def args(self, p):
        return []

    @_('"(" nonempty_args ")"')
    def args(self, p):
        return p.nonempty_args

    @_('declaration')
    def nonempty_args(self, p):
        return [p.declaration]

    @_('declaration "," nonempty_args')
    def nonempty_args(self, p):
        return [p.declaration] + p.nonempty_args

    @_('type PID "[" NUM_INT "]"')
    def declaration(self, p):
        self.local_arrays[p.PID] = p.type
        return {"type": p.type, "name": p.PID, "size": p.NUM}

    @_('type PID')
    def declaration(self, p):
        self.locals[p.PID] = p.type
        return Local(p.lineno, p.PID, p.type)

    @_('INT', 'FLOAT')
    def type(self, p):
        return p[0][0] + '32'

    @_('commands command')
    def commands(self, p):
        return p[0] + [p[1]]

    @_('command')
    def commands(self, p):
        return [p[0]]

    @_('identifier GETS expression')
    def command(self, p):
        return AssignCommand(p.lineno, p[0], p[2])

    @_('IF condition BEGIN commands END ELSE BEGIN commands END')
    def command(self, p):
        return IfCommand(p.condition, p[3], p[7])

    @_('IF condition BEGIN commands END')
    def command(self, p):
        return IfCommand(p.condition, p.commands, [])

    @_('WHILE condition BEGIN commands END')
    def command(self, p):
        resp = "while", p[1], p[3]
        return resp

    @_('FOR PID FROM value TO value BEGIN commands END')
    def command(self, p):
        resp = "forup", p[1], p[3], p[5], p[7]
        return resp

    @_('FOR PID FROM value DOWNTO value BEGIN commands END')
    def command(self, p):
        resp = "fordown", p[1], p[3], p[5], p[7]
        return resp

    @_('READ identifier')
    def command(self, p):
        return IOCommand(p.lineno, "read", p.identifier)

    @_('WRITE expression')
    def command(self, p):
        return IOCommand(p.lineno, "write", p.expression)

    @_('function_call')
    def command(self, p):
        return CallCommand(p.function_call)

    @_('RETURN expression')
    def command(self, p):
        return ReturnCommand(p.lineno, p.expression)

    @_('PID "(" ")"')
    def function_call(self, p):
        return FunctionCall(p.lineno, p.PID, [])

    @_('PID "(" args ")"')
    def function_call(self, p):
        return FunctionCall(p.lineno, p.PID, p.args)

    @_('value')
    def args(self, p):
        return [p.value]

    @_('args "," value')
    def args(self, p):
        return p.args + [p.value]

    @_('assignable_value')
    def expression(self, p):
        return p[0]

    @_('assignable_value "+" assignable_value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "add")

    @_('assignable_value "-" assignable_value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "sub")

    @_('assignable_value "*" assignable_value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "mul")

    @_('assignable_value "/" assignable_value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "div_u")

    @_('assignable_value "%" assignable_value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "rem_u")

    @_('assignable_value EQ assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "eq")

    @_('assignable_value NEQ assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "ne")

    @_('assignable_value LT assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "lt_u")

    @_('assignable_value GT assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "gt_u")

    @_('assignable_value LEQ assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "le_u")

    @_('assignable_value GEQ assignable_value')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "ge_u")

    @_("value", "function_call")
    def assignable_value(self, p):
        return p[0]

    @_('NUM_INT')
    def value(self, p):
        return Const(int(p[0]), "i32")

    @_('NUM_FLOAT')
    def value(self, p):
        return Const(float(p[0]), "f32")

    @_('identifier')
    def value(self, p):
        return p[0]

    @_('PID')
    def identifier(self, p):
        return Local(p.lineno, p.PID)

    @_('PID "[" PID "]"')
    def identifier(self, p):
        if p[0] in self.local_arrays:
            if p[2] in self.locals:
                return []  # TODO
            raise Exception(f"Unknown variable {p[2]}")
        raise Exception(f"Unknown array {p[0]}")

    @_('PID "[" NUM_INT "]"')
    def identifier(self, p):
        if p[0] in self.local_arrays:
            return []  # TODO
        raise Exception(f"Unknown array {p[0]}")

    def error(self, token):
        raise Exception(f"{token.lineno}: Syntax error '{token.value}'")


def parse(code: str):
    lex = ImpLexer()
    pars = ImpParser()
    tokens = lex.tokenize(code)
    return pars.parse(tokens).generate_code()
