from sly import Lexer, Parser

from wasm_generator import WasmGenerator


class ImpLexer(Lexer):
    # @_(r'\[[^\]]*\]')
    # def ignore_comment(self, t):
    #     self.lineno += t.value.count('\n')

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)

    tokens = {DEF, WITH, MAIN, BEGIN, END, PID, NUM, IF, ELSE, WHILE, FOR, FROM, TO,
              DOWNTO, READ, WRITE, CALL, EQ, NEQ, GT, LT, GEQ, LEQ, GETS, INT, FLOAT}

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
    CALL = r"call"

    NEQ = r"!="
    GEQ = r">="
    LEQ = r"<="
    EQ = r"=="
    GT = r">"
    LT = r"<"
    GETS = r"="
    MAIN = r"main"

    PID = r"[_a-z]+"

    @_(r'\d+')
    def NUM(self, t):
        t.value = int(t.value)
        return t

    def error(self, t):
        raise Exception(f"Illegal character '{t.value[0]}'")

    literals = {'+', '-', '*', '/', '%', ',', ';', '[', ']', '(', ')'}
    ignore = ' \t'


class ImpParser(Parser):
    debugfile = "parser.out"
    tokens = ImpLexer.tokens
    code = None

    @_('procedures main')
    def program(self, p):
        self.code = {"procedures": p[0], "main": p[1]}
        return self.code

    @_('')
    def procedures(self, p):
        return []

    @_('procedures procedure')
    def procedures(self, p):
        return p[0] + [p[1]]

    @_('DEF PID args declarations BEGIN commands END')
    def procedure(self, p):
        return {"name": p.PID, "args": p.args, "locals": p.declarations, "body": p.commands}

    @_('DEF MAIN "(" ")" declarations BEGIN commands END')
    def main(self, p):
        return {"name": "main", "locals": p.declarations, "body": p.commands}

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

    @_('type PID "[" NUM "]"')
    def declaration(self, p):
        return {"type": p.type, "name": p.PID, "size": p.NUM}

    @_('type PID')
    def declaration(self, p):
        return {"type": p.type, "name": p.PID}

    @_('INT', 'FLOAT')
    def type(self, p):
        return p[0][0] + '64'

    @_('commands command')
    def commands(self, p):
        return p[0] + [p[1]]

    @_('command')
    def commands(self, p):
        return [p[0]]

    @_('identifier GETS expression')
    def command(self, p):
        return "assign", p[0], p[2]

    @_('IF condition BEGIN commands ELSE commands END')
    def command(self, p):
        resp = "ifelse", p[1], p[3], p[5]
        return resp

    @_('IF condition BEGIN commands END')
    def command(self, p):
        resp = "if", p[1], p[3]
        return resp

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
        return "read", p[1]

    @_('WRITE value')
    def command(self, p):
        return "write", p[1]

    @_('CALL PID "(" args ")"')
    def command(self, p):
        return p

    @_('value')
    def args(self, p):
        return p[0]

    @_('args "," value')
    def args(self, p):
        return p[0]

    @_('value')
    def expression(self, p):
        return p[0]

    @_('value "+" value')
    def expression(self, p):
        return "add", p[0], p[2]

    @_('value "-" value')
    def expression(self, p):
        return "sub", p[0], p[2]

    @_('value "*" value')
    def expression(self, p):
        return "mul", p[0], p[2]

    @_('value "/" value')
    def expression(self, p):
        return "div", p[0], p[2]

    @_('value "%" value')
    def expression(self, p):
        return "mod", p[0], p[2]

    @_('value EQ value')
    def condition(self, p):
        return "eq", p[0], p[2]

    @_('value NEQ value')
    def condition(self, p):
        return "ne", p[0], p[2]

    @_('value LT value')
    def condition(self, p):
        return "lt", p[0], p[2]

    @_('value GT value')
    def condition(self, p):
        return "gt", p[0], p[2]

    @_('value LEQ value')
    def condition(self, p):
        return "le", p[0], p[2]

    @_('value GEQ value')
    def condition(self, p):
        return "ge", p[0], p[2]

    @_('NUM')
    def value(self, p):
        return "const", p[0]

    @_('identifier')
    def value(self, p):
        return "load", p[0]

    @_('PID')
    def identifier(self, p):
        return p[0]

    @_('PID "[" PID "]"')
    def identifier(self, p):
        return p[0], p[2]

    @_('PID "[" NUM "]"')
    def identifier(self, p):
        return p[0], p[2]

    def error(self, token):
        raise Exception(f"Syntax error: '{token.value}' in line {token.lineno}")


def parse(code: str):
    lex = ImpLexer()
    pars = ImpParser()
    tokens = lex.tokenize(code)
    pars.parse(tokens)
    generator = WasmGenerator(pars.code)
    return generator.code
