from sly import Lexer, Parser

from intermediate_code import Local, Const, AssignCommand, Expression, CallCommand, ReturnCommand, \
    Function, Module, FunctionCall, IfCommand, ForLoop, WhileLoop, Array, ReadCommand, WriteCommand, ArrayValue


class ImpLexer(Lexer):
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)

    tokens = {DEF, WITH, MAIN, BEGIN, END, PID, NUM_FLOAT, NUM_INT, IF, ELSE, WHILE, FOR, FROM, TO,
              DOWNTO, READ, WRITE, RETURN, EQ, NEQ, GT, LT, GEQ, LEQ, GETS, INT, FLOAT, ARRAYS}

    DEF = r"def"
    WITH = r"with"
    BEGIN = r"{"
    INT = r"int"
    FLOAT = r"float"
    ARRAYS = r"arrays"

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

    PID = r"[_A-Za-z]+"

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
        self.code = None

    @_('array_declarations functions main')
    def program(self, p):
        return Module(p.array_declarations, p.functions + [p.main])

    @_('')
    def functions(self, p):
        return []

    @_('functions function')
    def functions(self, p):
        return p[0] + [p[1]]

    @_('DEF PID args declarations BEGIN commands END')
    def function(self, p):
        return Function(p.lineno, p.PID, p.args, p.declarations, p.commands)

    @_('type PID args declarations BEGIN commands END')
    def function(self, p):
        return Function(p.lineno, p.PID, p.args, p.declarations, p.commands, p.type)

    @_('DEF MAIN "(" ")" declarations BEGIN commands END')
    def main(self, p):
        return Function(p.lineno, "main", [], p.declarations, p.commands)

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

    @_('')
    def array_declarations(self, p):
        return []

    @_('ARRAYS array_declaration more_array_declarations')
    def array_declarations(self, p):
        return [p.array_declaration] + p.more_array_declarations

    @_('"," array_declaration more_array_declarations')
    def more_array_declarations(self, p):
        return [p.array_declaration] + p.more_array_declarations

    @_('')
    def more_array_declarations(self, p):
        return []

    @_('type PID "[" NUM_INT "]"')
    def array_declaration(self, p):
        return Array(p.lineno, p.PID, p.type, p.NUM_INT)

    @_('type PID')
    def declaration(self, p):
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
        return WhileLoop(p.lineno, p.condition, p.commands)

    @_('FOR PID FROM expression TO expression BEGIN commands END')
    def command(self, p):
        return ForLoop(p.lineno, p.PID, p[3], p[5], "up", p[7])

    @_('FOR PID FROM expression DOWNTO expression BEGIN commands END')
    def command(self, p):
        return ForLoop(p.lineno, p.PID, p[3], p[5], "down", p[7])

    @_('READ identifier')
    def command(self, p):
        return ReadCommand(p.lineno, p.identifier)

    @_('WRITE expression')
    def command(self, p):
        return WriteCommand(p.lineno, p.expression)

    @_('function_call')
    def command(self, p):
        return CallCommand(p.function_call)

    @_('RETURN expression')
    def command(self, p):
        return ReturnCommand(p.lineno, p.expression)

    @_('RETURN ";"')
    def command(self, p):
        return ReturnCommand(p.lineno, None)

    @_('PID "(" ")"')
    def function_call(self, p):
        return FunctionCall(p.lineno, p.PID, [])

    @_('PID "(" call_args ")"')
    def function_call(self, p):
        return FunctionCall(p.lineno, p.PID, p.call_args)

    @_('expression')
    def call_args(self, p):
        return [p.expression]

    @_('call_args "," expression')
    def call_args(self, p):
        return p.call_args + [p.expression]

    @_('value')
    def expression(self, p):
        return p[0]

    @_('value "+" value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "add")

    @_('value "-" value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "sub")

    @_('value "*" value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "mul")

    @_('value "/" value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "div_s")

    @_('value "%" value')
    def expression(self, p):
        return Expression(p.lineno, (p[0], p[2]), "rem_s")

    @_('expression EQ expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "eq")

    @_('expression NEQ expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "ne")

    @_('expression LT expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "lt_s")

    @_('expression GT expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "gt_s")

    @_('expression LEQ expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "le_s")

    @_('expression GEQ expression')
    def condition(self, p):
        return Expression(p.lineno, (p[0], p[2]), "ge_s")

    @_('function_call')
    def value(self, p):
        return p[0]

    @_('"-" NUM_INT')
    def value(self, p):
        return Const(-int(p[1]), "i32")

    @_('NUM_INT')
    def value(self, p):
        return Const(int(p[0]), "i32")

    @_('"-" NUM_FLOAT')
    def value(self, p):
        return Const(-float(p[1]), "f32")

    @_('NUM_FLOAT')
    def value(self, p):
        return Const(float(p[0]), "f32")

    @_('identifier')
    def value(self, p):
        return p[0]

    @_('PID')
    def identifier(self, p):
        return Local(p.lineno, p.PID)

    @_('PID "[" expression "]"')
    def identifier(self, p):
        return ArrayValue(p.lineno, p.PID, p.expression)

    def error(self, token):
        raise Exception(f"{token.lineno}: Syntax error '{token.value}'")


def parse(code: str):
    lex = ImpLexer()
    pars = ImpParser()
    tokens = lex.tokenize(code)
    return pars.parse(tokens).generate_code()
