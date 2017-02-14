# Config Lexer
# A configuration file lexer for headcount.conf
# File Creation Date: 2017-02-03
# Last Modified Date: 2017-02-03

from ply import lex
from ply import yacc

tokens = (
    "COMMENT",
    "TOKROOMSTART",
    "TOKROOMEND",
    "TOKOCCUPANCY",
    "TOKNICK",
    "TOKSVGID",
    "INT",
    "STRING",
)

t_TOKROOMSTART = r"room"

t_TOKROOMEND = r"moor"

t_TOKOCCUPANCY = r"max-occupancy"

t_TOKNICK = r"nickname"

t_TOKSVGID = r"svg-id"

t_ignore_WHITESPACE = r"[\n \t]+"


# Comments are a pound sign, followed by any number of characters up to the end of the line
def t_COMMENT(t):
    r"""\#.*"""
    pass


# Integers are one or more digits, converted to a python int
def t_INT(t):
    r"\d+"
    t.value = int(t.value)
    return t


# Strings are any number of letters, numbers, and keyboard special characters
def t_STRING(t):
    r"""\"[A-z0-9\-_ '%\.,/:;<>!@#$^&\*\(\)+=]*\""""
    t.value = t.value[1:-1]
    return t


# Raise an error when something can't be parsed
def t_error(t):
    raise TypeError("Unable to lexically parse the text starting at '%s'." % (t.value,))

# Create the lexer
lexer = lex.lex()
text = ""
with open("headcount.conf", "r") as f:
    text = f.read()
#     lexer.input(text)
#     for token in lexer:
#         print(token)


# Store the rooms in an object
class Room(object):
    def __init__(self, name, max_occupancy, svg_id, nickname=""):
        self.name = name
        self.max_occupancy = max_occupancy
        self.svg_id = svg_id
        self.nickname = nickname

    def __repr__(self):
        return "Room( name=\"%s\", max_occupancy=%s, svg_id=\"%s\", nickname=\"%s\" )" % (
            self.name,
            self.max_occupancy,
            self.svg_id,
            self.nickname
        )


def p_room_set(p):
    """room_set : room
                | room_set room"""
    if len(p) > 2:
        p[0] = p[1]
        p[0].append(p[2])
    elif len(p) == 2:
        p[0] = [p[1], ]


def p_room(p):
    """room : TOKROOMSTART STRING config_group TOKROOMEND"""
    if "nickname" in p[3].keys():
        p[0] = Room(p[2], p[3]["max-occupancy"], p[3]["svg-id"], nickname=p[3]["nickname"])
    else:
        p[0] = Room(p[2], p[3]["max-occupancy"], p[3]["svg-id"])


def p_config_group(p):
    """config_group : config_phrase
                    | config_group config_phrase"""
    # If there's already a config group there, add the new item to it
    if len(p) > 2:
        # Take the first element of the tuple in p[2] (the token value) and use it as a new key in the dictionary in
        # p[1]. Assign the value from the second element in the tuple in p[2] (the associated string/int) to that
        # dictionary key
        # Yes, I know this line is horribly opaque
        p[1][p[2][0]] = p[2][1]
        # Put p[1] into p[0], as required by Yacc
        p[0] = p[1]
    # Otherwise, make a dict and put the new phrase into it
    elif len(p) == 2:
        p[0] = {p[1][0]: p[1][1]}


def p_config_phrase(p):
    """config_phrase : TOKOCCUPANCY INT
                     | TOKNICK STRING
                     | TOKSVGID STRING"""
    # Store the token name and it's value in a tuple
    p[0] = (p[1], p[2])


def p_error(p):
    raise SyntaxError("Shit's broke, son.")


def read_configuration():
    parser = yacc.yacc(debug=1)
    return parser.parse(text, lexer=lexer)

