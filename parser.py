from sly import Lexer, Parser


class ImpLexer(Lexer):
    @_(r'\[[^\]]*\]')
    def ignore_comment(self, t):
        self.lineno += t.value.count('\n')

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)

    tokens = {DEF, MAIN, BEGIN, END, PID, NUM, IF, THEN, ELSE, ENDIF, WHILE, DO, ENDWHILE, FOR, FROM, TO,
              DOWNTO, ENDFOR, READ, WRITE, CALL, EQ, NEQ, GT, LT, GEQ, LEQ, GETS, INT, FLOAT}

    DEF = r"DEF"
    BEGIN = r"BEGIN"
    INT = r"INT"
    FLOAT = r"FLOAT"

    ENDWHILE = r"ENDWHILE"
    ENDFOR = r"ENDFOR"
    ENDIF = r"ENDIF"
    END = r"END"

    WHILE = r"WHILE"
    FOR = r"FOR"
    IF = r"IF"

    THEN = r"THEN"
    ELSE = r"ELSE"

    DOWNTO = r"DOWNTO"
    DO = r"DO"
    TO = r"TO"

    FROM = r"FROM"

    READ = r"READ"
    WRITE = r"WRITE"
    CALL = r"CALL"

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
    tokens = ImpLexer.tokens
    code = None
    consts = set()

    @_('procedures main')
    def program(self, p):
        self.code = tuple(p)
        return p[0], p[1]

    @_('')
    def procedures(self, p):
        return []

    @_('procedures procedure')
    def procedures(self, p):
        return p[0] + [p[1]]

    @_('DEF PID "(" declarations ")" declarations BEGIN commands END')
    def procedure(self, p):
        return " ".join(str(e) for e in p)

    @_('DEF MAIN "(" ")" declarations BEGIN commands END')
    def main(self, p):
        return tuple(p)

    @_('')
    def declarations(self, p):
        return []

    @_('declarations declaration')
    def declarations(self, p):
        return p[0] + [p[1]]

    @_('type PID ";"')
    def declaration(self, p):
        return tuple(p)

    @_('type PID "[" NUM "]" ";"')
    def declaration(self, p):
        return tuple(p)

    @_('INT', 'FLOAT')
    def type(self, p):
        return p[0]

    @_('commands command')
    def commands(self, p):
        return p[0] + [p[1]]

    @_('command')
    def commands(self, p):
        return [p[0]]

    @_('identifier GETS expression ";"')
    def command(self, p):
        return "assign", p[0], p[2]

    @_('IF condition THEN commands ELSE commands ENDIF')
    def command(self, p):
        resp = "ifelse", p[1], p[3], p[5], self.consts.copy()
        self.consts.clear()
        return resp

    @_('IF condition THEN commands ENDIF')
    def command(self, p):
        resp = "if", p[1], p[3], self.consts.copy()
        self.consts.clear()
        return resp

    @_('WHILE condition DO commands ENDWHILE')
    def command(self, p):
        resp = "while", p[1], p[3], self.consts.copy()
        self.consts.clear()
        return resp

    @_('FOR PID FROM value TO value DO commands ENDFOR')
    def command(self, p):
        resp = "forup", p[1], p[3], p[5], p[7], self.consts.copy()
        self.consts.clear()
        return resp

    @_('FOR PID FROM value DOWNTO value DO commands ENDFOR')
    def command(self, p):
        resp = "fordown", p[1], p[3], p[5], p[7], self.consts.copy()
        self.consts.clear()
        return resp

    @_('READ identifier ";"')
    def command(self, p):
        return "read", p[1]

    @_('WRITE value ";"')
    def command(self, p):
        if p[1][0] == "const":
            self.consts.add(int(p[1][1]))
        return "write", p[1]

    @_('CALL PID "(" args ")" ";"')
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
        # if p[0] in self.symbols:
        #     return p[0]
        # else:
        #     return "undeclared", p[0]

    @_('PID "[" PID "]"')
    def identifier(self, p):
        return p[0], p[2]
        # if p[0] in self.symbols and type(self.symbols[p[0]]) == Array:
        #     if p[2] in self.symbols and type(self.symbols[p[2]]) == Variable:
        #         return "array", p[0], ("load", p[2])
        #     else:
        #         return "array", p[0], ("load", ("undeclared", p[2]))
        # else:
        #     raise Exception(f"Undeclared array {p[0]}")

    @_('PID "[" NUM "]"')
    def identifier(self, p):
        return p[0], p[2]
        # if p[0] in self.symbols and type(self.symbols[p[0]]) == Array:
        #     return "array", p[0], p[2]
        # else:
        #     raise Exception(f"Undeclared array {p[0]}")

    def error(self, token):
        raise Exception(f"Syntax error: '{token.value}' in line {token.lineno}")


def parse(code: str):
    lex = ImpLexer()
    pars = ImpParser()

    pars.parse(lex.tokenize(code))
    return str(pars.code)

