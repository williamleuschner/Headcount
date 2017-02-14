# Headcount.py
# A Server-Side Python Application for Labbies Taking Headcounts in SE Classrooms
# Author: William Leuschner
# File Creation Date: 2017-02-01
# Last Modified Date: 2017-02-01

from flask import Flask
import config_lexer

app = Flask(__name__)

@app.route("/")
def hello_world():
    return("Hello, world!")


def main():
    config = config_lexer.read_configuration()

main()
