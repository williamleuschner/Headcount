# Headcount.py
# A Server-Side Python Application for Labbies Taking Headcounts in SE
# Classrooms
# Author: William Leuschner
# File Creation Date: 2017-02-01
# Last Modified Date: 2017-02-21

import os

from flask import Flask, request, render_template, redirect, session, \
    make_response, url_for, g

from urllib.parse import urlparse

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from functools import update_wrapper, wraps

import config_lexer
import hc_db
import datetime
import re

from collections import namedtuple, OrderedDict

app = Flask(__name__)

app.config['SAML_PATH'] = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'saml'
)
app.secret_key = "::06%grown%GREEK%play%95::"
#################################
#      WARNING: DULL EDGES!     #
# This shouldn't be hard-coded. #
#################################
app.config['DATABASE'] = "../db/hc.db"
#################################
#     WARNING: SHARP EDGES!     #
#   SET TO FALSE IN PRODUCTION  #
#   I think it's obvious why.   #
#################################
app.config['DISABLE_AUTH'] = True

NavButton = namedtuple("NavButton", "location name")

USERNAME_REGEX = re.compile(r"^[a-z]{3}([a-z]{3}|[0-9]{4})$")


def connect_db():
    """Connects to the application database"""
    return hc_db.HCDB(app.config['DATABASE'])


@app.teardown_appcontext
def close_db(error):
    """Closes the database connection at the end of the request"""
    if hasattr(g, 'sql_db'):
        g.sql_db.close()


def get_db():
    """Get a database connection. Create a new one if one doesn't already
    exist for the current app context."""
    if not hasattr(g, 'sql_db'):
        g.sql_db = connect_db()
    return g.sql_db


@app.cli.command("initdb")
def initdb_command():
    """Initialize the database"""
    db = get_db()
    with app.open_resource('../db/hc.schema', mode='r') as f:
        db.initialize(f)


def validate_username(test_string: str) -> bool:
    """Test to make sure the username provided could be a valid RIT username
    :return True if the username is OK, False if it isn't"""
    return USERNAME_REGEX.match(test_string) is not None


def is_admin(username: str) -> bool:
    """Returns True if the user is an administrator, False if they are not (
    or if they don't exist, since non-existent users cannot be 
    administrators."""
    db = get_db()
    return int(db.get_user_by_name(username)['is_admin']) == 1


def authenticated(decoratee):
    """Decorator to check whether the user is authenticated"""
    @wraps(decoratee)
    def wrapper(*args, **kwargs):
        if "username" in session.keys():
            return decoratee(*args, **kwargs)
        else:
            return redirect(url_for("login"))
    return wrapper


def admin_authenticated(decoratee):
    """Decorator to check whether the user is authenticated and an 
    administrator"""
    @wraps(decoratee)
    def wrapper(*args, **kwargs):
        if "username" in session.keys():
            if is_admin(session['username']):
                return decoratee(*args, **kwargs)
            else:
                session["last_error"] = "You need to be an administrator to " \
                                        "view this page."
                return redirect(url_for("error"))
        else:
            return redirect(url_for("login"))
    return wrapper


def init_saml_auth(req):
    auth = OneLogin_Saml2_Auth(req, custom_base_path=app.config['SAML_PATH'])
    return auth


def prepare_flask_request(req):
    url_data = urlparse(req.url)
    return {
        'https': "on" if req.scheme == 'https' else "off",
        'http_host': req.host,
        'server_port': url_data.port,
        'script_name': req.path,
        'get_data': req.args.copy(),
        'post_data': req.form.copy()
    }


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    req = prepare_flask_request(request)
    auth = init_saml_auth(req)
    errors = []
    not_auth_warn = False
    success_slo = False
    attributes = False
    paint_logout = False

    if not app.config['DISABLE_AUTH']:
        if 'sso' in request.args:
            return redirect(auth.login())
        elif 'sso2' in request.args:
            return_to = '%sattrs/' % request.host_url
            return redirect(auth.login(return_to))
        elif 'slo' in request.args:
            name_id = None
            session_index = None
            if 'samlNameId' in session:
                name_id = session['samlNameId']
            if 'samlSessionIndex' in session:
                session_index = session['samlSessionIndex']

            return redirect(
                auth.logout(name_id=name_id, session_index=session_index))
        elif 'acs' in request.args:
            auth.process_response()
            errors = auth.get_errors()
            not_auth_warn = not auth.is_authenticated()
            if len(errors) == 0:
                session['samlUserdata'] = auth.get_attributes()
                session['samlNameId'] = auth.get_nameid()
                session['samlSessionIndex'] = auth.get_session_index()
                self_url = OneLogin_Saml2_Utils.get_self_url(req)
                if (
                                'RelayState' in request.form and
                                self_url != request.form['RelayState']
                ):
                    return redirect(auth.redirect_to(request.form['RelayState']))
        elif 'sls' in request.args:
            # Activating the Space Launch System...
            dscb = lambda: session.clear()
            url = auth.process_slo(delete_session_cb=dscb)
            errors = auth.get_errors()
            if len(errors) == 0:
                if url is not None:
                    return redirect(url)
                else:
                    success_slo = True

        if 'samlUserdata' in session:
            paint_logout = True
            if len(session['samlUserdata']) > 0:
                attributes = session['samlUserdata'].items()

        return redirect(url_for("index"))
    else:
        session['username'] = "wel2138"
        session['log_rows'] = 3
        return redirect(url_for('show_main'))


@app.route("/main")
@authenticated
def show_main():
    # If there is no submit argument, just render the page
    if request.args.get("submit", "") == "":
        db = get_db()
        now = datetime.datetime.now()
        rooms = [room for room in app.config["HC_CONFIG"]]
        rooms.sort(key=config_lexer.Room.sortkey)
        # Get the three newest counts from the database, sorted by the
        # user-provided time
        newest_counts = db.get_newest_counts(3, hc_db.NewestSort.ENTERED_TIME)
        recent_counts = []
        for count in newest_counts:
            room_rows = db.get_roomdata_for_count_id(count['id'])
            # I couldn't think of a short, descriptive name for this variable.
            some_dict = {"date": count['entered_time'], "counts": {}}
            for row in room_rows:
                some_dict["counts"][row['room']] = row['people_count']
            some_dict['counts'] = OrderedDict(sorted(some_dict['counts'].items()))
            recent_counts.append(some_dict)
        return render_template(
            "main.html",
            buttons=[
                NavButton(url_for("logout"), "Log Out"),
                NavButton(url_for("show_admin"), "Administration"),
                NavButton(url_for("help"), "Help")
            ],
            rooms=rooms,
            recent_counts=recent_counts,
            datewhen=now.strftime("%Y-%m-%d"),
            timewhen=now.strftime("%H:%M:%S")
        )
    else:
        # Otherwise, add a new headcount and then redirect to the same page, but
        # without arguments
        db = get_db()
        # TODO: Data validation might be important, maybe.
        if (request.args.get("date") is None or
            request.args.get("time") is None
           ):
            session["last_error"] = "Submitted headcounts must have a time " \
                                    "associated with them, and the request " \
                                    "you just made didn't."
            return redirect(url_for('error'))
        provided_time = datetime.datetime.strptime(
            # This doesn't use .get() on purpose. Things should break if there
            # is no data here
            request.args['date'] + "T" + request.args['time'],
            "%Y-%m-%dT%H:%M:%S"
        )
        current_time = datetime.datetime.now()
        # Copy the request arguments
        counts = dict(request.args)
        # Delete the ones that I don't need
        del(counts['date'])
        del(counts['time'])
        del(counts['submit'])
        # TODO: This shouldn't be hardcoded to my username
        user = db.get_user_by_name(session['username'])
        # Give those arguments to the database
        db.add_headcount(user['id'], current_time, provided_time, counts)
        return redirect(url_for('show_main'))


def get_csv_logs(how_many_rows: int) -> str:
    """Get the logs from the database and convert them into CSV"""
    db = get_db()
    counts = db.get_newest_counts(how_many_rows, hc_db.NewestSort.SUBMIT_TIME)
    counts_as_string = ""
    for count in counts:
        username = db.get_user_by_id(count['user_id'])['username']
        room_rows = db.get_roomdata_for_count_id(count['id'])
        counts_as_string += username + ","
        counts_as_string += count['submit_time'] + "," + \
                            count['entered_time'] + ","
        room_counts = {}
        for row in room_rows:
            room_counts[row['room']] = row['people_count']
        room_counts = OrderedDict(sorted(room_counts.items()))
        counts_as_string += ",".join([str(x) for x in room_counts.values()])
        counts_as_string += "\n"
    return counts_as_string


def render_admin_page(template_name: str):
    """Render an admin page, since this code gets repeated three times"""
    db = get_db()
    usernames = [u['username'] for u in db.get_all_users(False)]
    adminnames = [a['username'] for a in db.get_all_users(True)]
    return render_template(
        template_name,
        users=usernames,
        admins=adminnames,
        logs=get_csv_logs(session['log_rows']),
        log_rows=int(session['log_rows']),
        buttons=[
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("help"), "Help")
        ],
    )


@app.route("/admin")
@admin_authenticated
def show_admin():
    do_update_rows = request.args.get("update-rows")
    new_rows = request.args.get("rows")
    if do_update_rows is not None and new_rows is not None:
        session['log_rows'] = new_rows
    return render_admin_page("admin.html")


def add_user(usernames: list, admin: bool) -> bool:
    """Validate, then add, a new user"""
    db = get_db()
    for name in usernames:
        # If it's a valid username,
        if validate_username(name):
            # Add it to the database
            db.add_user(name, is_admin=admin)
            return True
    return False


def user_management_handler(template: str, redir_page: str,
                            new_users_field_name: str, admins: bool):
    """The two admin editing pages are basically the same, except for some
    slightly different variable names. So, I rolled them into this function."""
    # Get a DB connection
    db = get_db()
    # The arguments should have a key "add" if the user clicked the "+" button
    if request.args.get("add") is not None:
        # In a well-formatted request, this is a comma-separated list
        new_users = request.args.get(new_users_field_name)
        # Split into a list
        new_users_l = new_users.split(",")
        # Add all of those users
        add_user(new_users_l, admins)
        # Strip all of the request stuff off of the url
        return redirect(url_for(redir_page))
    elif request.args.get('delete') is not None:
        # The arguments should have a key "delete" if the user clicked the
        # trash bin
        # Copy the request, since we need to make changes
        args_copy = dict(request.args)
        # Delete this key, since we don't need it
        del args_copy["delete"]
        # If the request also has a new_admins key, delete that too
        if new_users_field_name in args_copy.keys():
            del args_copy[new_users_field_name]
        # For all of the remaining keys,
        for user in args_copy.keys():
            # If it is a valid username and that users is in the database,
            if validate_username(user) and db.does_user_exist(user):
                # Delete them.
                db.del_user(user)
        return redirect(url_for(redir_page))
    else:
        return render_admin_page(template)


@app.route("/admin/edit-admins")
@admin_authenticated
def show_admin_edit_admins():
    # TODO: This doesn't update the value that's displayed. Fix!
    do_update_rows = request.args.get("update-rows")
    new_rows = request.args.get("rows")
    if do_update_rows is not None and new_rows is not None:
        session['log_rows'] = new_rows
    return user_management_handler("admin-ea.html", "show_admin_edit_admins",
                            "new_admins", True)


@app.route("/admin/edit-users")
@admin_authenticated
def show_admin_edit_users():
    do_update_rows = request.args.get("update-rows")
    new_rows = request.args.get("rows")
    if do_update_rows is not None and new_rows is not None:
        session['log_rows'] = new_rows
    return user_management_handler("admin-eu.html", "show_admin_edit_users",
                            "new_users", False)


@app.route("/logout")
def logout():
    del(session['username'])
    if not app.config["DISABLE_AUTH"]:
        pass
    else:
        return redirect(url_for('index'))


@app.route("/help")
def help():
    return "<!DOCTYPE html><html lang='en'><head><title>Help</title><meta " \
           "charset='utf-8'></head><body><h1>Help</h1><p>Currently, I haven't" \
           " written a help page yet.</p></body></html>"


@app.route("/error")
def error():
    return render_template(
        'error.html',
        message=session["last_error"] if "last_error" in session.keys() else
        "An unspecified error occurred.",
        buttons=[
                NavButton(url_for("logout"), "Log Out"),
                NavButton(url_for("show_main"), "Main"),
                NavButton(url_for("help"), "Help")
            ]
    )


def main():
    app.config["HC_CONFIG"] = config_lexer.read_configuration()

main()
