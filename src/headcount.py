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

@app.route("/main")
def show_main():
    return("This is the main count entry screen")

@app.route("/admin")
def show_admin():
    return("This is the administration page")

@app.route("/admin/edit-admins")
def show_admin_edit_admins():
    return("This is the administration page, but in edit mode for administrators")

@app.route("/admin/edit-users")
def show_admin_edit_users():
    return("This is the administration page, but in edit mode for users")


def main():
    config = config_lexer.read_configuration()

main()
