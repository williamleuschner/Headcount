# lexer-test.py
# Testing out a python lexer
# Author: William Leuschner
# File Creation Date: 2017-02-01
# Last Modified Date: 2017-02-01

from ply import lex
from ply import yacc

tokens = [
    "FLOAT",
    "INT",
    "OPERATOR",
    "OPEN_GROUP",
    "CLOSE_GROUP",
]


def t_FLOAT(t):
    r"\d+[.]\d*"
    t.value = float(t.value)
    return t


def t_INT(t):
    r"\d+"
    t.value = int(t.value)
    return t

t_OPERATOR = r"[\+-\*/%]"

t_OPEN_GROUP = r"[\(\[\{]"

t_CLOSE_GROUP = r"[\]\)\}]"


def t_error(t):
    raise TypeError("Unknown text '%s'" % (t.value,))

lex.lex()

# lex.input("4+5*32-4/6")
# lex.input("200.316*6000-0.0013")
# lex.input("This should fail")
# lex.input("Does this 026 work?")
# lex.input("(212*6)-32")
# for tok in iter(lex.token, None):
#     print(repr(tok.type), repr(tok.value))


class Expression(object):
    def __init__(self, operator, operand1, operand2):
        self.operator = operator
        self.op1 = operand1
        self.op2 = operand2
        self.actions = {"+": self.add, "-": self.sub, "*": self.mult, "/": self.div}

    def __repr__(self):
        return "Expression(%s %s %s)" % (self.op1, self.operator, self.op2)

    def add(self):
        return self.op1.compute() + self.op2.compute()

    def sub(self):
        return self.op1.compute() - self.op2.compute()

    def mult(self):
        return self.op1.compute() * self.op2.compute()

    def div(self):
        return self.op1.compute() / self.op2.compute()

    def compute(self):
        return self.actions[self.operator]


class UnaryExpression(Expression):
    def __init__(self, number):
        self.number = number

    def __repr__(self):
        return "UnaryExpression(%s)" % (self.number,)

    def compute(self):
        return self.number


def p_math_sequence(p):
    """
    math_sequence :
    """


def p_grouped_expression(p):
    """
    grouped_expression : OPEN_GROUP expression CLOSE_GROUP
    """


def p_single_expression(p):
    """
    expression : INT OPERATOR INT
    expression : FLOAT OPERATOR INT
    expression : INT OPERATOR FLOAT
    expression : FLOAT OPERATOR FLOAT
    """


def p_error(p):
    raise TypeError("Mathematical syntax error at %r" % (p.value, ))
