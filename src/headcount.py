# Headcount.py
# A Server-Side Python Application for Labbies Taking Headcounts in SE
# Classrooms
# Author: William Leuschner
# File Creation Date: 2017-02-01
# Last Modified Date: 2018-03-05
# To Whomever Needs To Maintain This In The Future: Sorry. I've learned a lot
#  about how to design applications since I wrote this, and it should
# probably be rewritten. For starters, it's mostly functional, instead of
# object-oriented. Hopefully that helps you understand some of the,
# in hindsight, rather braindead architectural decisions.

import datetime
import os
import re
import sys
from collections import namedtuple, OrderedDict
from functools import wraps
from sqlite3 import IntegrityError
from urllib.parse import urlparse

import click
from flask import Flask, request, render_template, redirect, session, \
    url_for, g, make_response
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

import config_lexer
import hc_db

app = Flask(__name__)

app.config['SAML_PATH'] = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'saml'
)
#################################
#      WARNING: DULL EDGES!     #
# These shouldn't be hard-coded.#
#################################
app.config['DATABASE'] = "../db/hc.db"
app.secret_key = os.environ["HEADCOUNT_SECRET_KEY"]
#################################
#     WARNING: SHARP EDGES!     #
#   SET TO FALSE IN PRODUCTION  #
#   I think it's obvious why.   #
#################################
app.config['DISABLE_AUTH'] = False
app.config['AUTH_NAME_TOGGLE'] = False

NavButton = namedtuple("NavButton", "location name")

USERNAME_REGEX = re.compile(r"^[a-z]{2,3}([a-z]{3}|[0-9]{4})$")

allowed_row_counts = [3, 5, 10, 30, 100]


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


def add_user(usernames: list, admin: bool):
    """Validate, then add, a new user"""
    db = get_db()
    for name in usernames:
        # If it's a valid username,
        if validate_username(name):
            # Add it to the database
            db.add_user(name, is_admin=admin)


@app.cli.command("initdb")
def initdb_command():
    """Initialize the database"""
    db = get_db()
    with app.open_resource('../db/hc.sql', mode='r') as f:
        db.initialize(f)


@app.cli.command("add_admin")
@click.argument("username")
def add_admin_command(username):
    """Set the given username as an administrator in the database"""
    try:
        if add_user([username, ], True):
            print("Successfully added %s as an administrator." % (username,))
        else:
            print("Failed to add %s as an administrator. Have you run the "
                  "initdb command? Are you sure that string fits the RIT "
                  "username format?" % (username,))
    except IntegrityError:
        print("%s is already an administrator. No action taken." % (username,))
        sys.exit(2)


def validate_username(test_string: str) -> bool:
    """Test to make sure the username provided could be a valid RIT username
    :return True if the username is OK, False if it isn't"""
    if USERNAME_REGEX.match(test_string) is not None:
        return True
    else:
        session['last_error'] = "That's not a valid username."
        return False


def is_admin(username: str) -> bool:
    """Returns True if the user is an administrator, False if they are not (
    or if they don't exist, since non-existent users cannot be 
    administrators."""
    db = get_db()
    return int(db.get_user_by_name(username)['is_admin']) == 1


def is_user(username: str) -> bool:
    """Returns True if the user is in the database, False if they are not."""
    db = get_db()
    if username is None:
        return False
    return not db.get_user_by_name(username) is None


def authenticated(decoratee):
    """Decorator to check whether the user is authenticated"""

    @wraps(decoratee)
    def wrapper(*args, **kwargs):
        if "username" in session.keys() and is_user(session['username']):
            return decoratee(*args, **kwargs)
        else:
            session["last_error"] = "You need to be logged in to view this " \
                                    "page."
            return redirect(url_for("error"))

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
            return redirect(url_for("login") + "?sso")

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


@app.route("/index")
def index():
    return render_template('index.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    if not app.config['DISABLE_AUTH']:
        req = prepare_flask_request(request)
        auth = init_saml_auth(req)
        errors = []
        success_slo = False

        if 'sso' in request.args:
            return_to = '%smain' % request.host_url
            return redirect(auth.login(return_to=return_to))
        elif 'slo' in request.args:
            name_id = session['samlNameId'] if 'samlNameId' in session \
                else None
            session_index = session['samlSessionIndex'] if 'samlSessionIndex' \
                                                           in session else None
            return redirect(
                auth.logout(name_id=name_id, session_index=session_index))
        elif 'acs' in request.args:
            auth.process_response()
            errors = auth.get_errors()
            if len(errors) == 0:
                if not auth.is_authenticated():
                    session["last_error"] = "RIT's Single-Sign On service " \
                                            "says that you're not " \
                                            "authenticated!"
                    return redirect(url_for("error"))
                session['samlUserdata'] = auth.get_attributes()
                session['samlNameId'] = auth.get_nameid()
                session['samlSessionIndex'] = auth.get_session_index()
                session['username'] = session['samlUserdata'].get(
                    "urn:oid:0.9.2342.19200300.100.1.1")[0]
                session["log_rows"] = 3
                if not is_user(session['username']):
                    session['last_error'] = "Unfortunately, you're not an " \
                                            "authorized user of this " \
                                            "application."
                    return redirect(url_for("error"))
                self_url = OneLogin_Saml2_Utils.get_self_url(req)
                if (
                        'RelayState' in request.form and
                        self_url != request.form['RelayState']
                ):
                    return redirect(
                        auth.redirect_to(request.form['RelayState']))
            else:
                session["last_error"] = "There was an error while handling the" \
                                        " SAML response: " + str(
                    auth.get_last_error_reason())
                return redirect(url_for("error"))
        elif 'sls' in request.args:
            dscb = lambda: session.clear()
            url = auth.process_slo(delete_session_cb=dscb)
            errors = auth.get_errors()
            if len(errors) == 0:
                if url is not None:
                    return redirect(url)
                else:
                    success_slo = True

        return redirect(url_for("index"))
    else:
        print("WARNING: AUTHENTICATION IS DISABLED. IF THIS MESSAGE APPEARS "
              "IN YOUR PRODUCTION LOGS, SOMETHING IS WRONG.")
        session['username'] = "tstusr" if not app.config['AUTH_NAME_TOGGLE'] \
            else "wel2138"
        app.config['AUTH_NAME_TOGGLE'] = not app.config['AUTH_NAME_TOGGLE']
        session['log_rows'] = 3
        return redirect(url_for('show_main'))


@app.route("/metadata/")
def metadata():
    req = prepare_flask_request(request)
    auth = init_saml_auth(req)
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)

    if len(errors) == 0:
        resp = make_response(metadata, 200)
        resp.headers['Content-Type'] = "text/xml"
    else:
        resp = make_response(', '.join(errors), 500)
    return resp


def try_strptime(s: str, fmt: str) -> datetime.datetime:
    """
    Attempt to parse the string s as a timestamp in the format specified by
    format.  Returns None if parsing fails.
    :param s: The time string to parse
    :param fmt: The format string with which to parse s
    :return: A datetime, or None if parsing failed.
    """
    try:
        return datetime.datetime.strptime(s, fmt)
    except ValueError:
        return None


def sort_count_data(item):
    room = app.config["HC_CONFIG"][item[0]]
    return config_lexer.Room.sortkey(room)


@app.route("/main", methods=['GET'])
@authenticated
def show_main():
    db = get_db()
    now = datetime.datetime.now()
    rooms = [room for room in app.config["HC_CONFIG"].values()]
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
        some_dict['counts'] = OrderedDict(
            sorted(some_dict['counts'].items(), key=sort_count_data)
        )
        recent_counts.append(some_dict)
    if is_admin(session['username']):
        buttons = [
            NavButton(url_for("show_admin"), "Administration"),
            NavButton(url_for("show_help"), "Help"),
            NavButton(url_for("logout"), "Log Out")
        ]
    else:
        buttons = [
            NavButton(url_for("show_help"), "Help"),
            NavButton(url_for("logout"), "Log Out")
        ]
    return render_template(
        "main.html",
        buttons=buttons,
        rooms=rooms,
        recent_counts=recent_counts,
        datewhen=now.strftime("%Y-%m-%d"),
        timewhen=now.strftime("%H:%M")
    )


@app.route("/submit", methods=['POST'])
@authenticated
def submit_headcount():
    db = get_db()
    if (
            request.form.get("date") is None or
            request.form.get("time") is None
    ):
        session["last_error"] = "Submitted headcounts must have a time " \
                                "associated with them, and the request " \
                                "you just made didn't."
        return redirect(url_for('error'))
    provided_time = try_strptime(
        request.form['date'] + "T" + request.form['time'],
        "%Y-%m-%dT%H:%M:%S"
    )
    if provided_time is None:
        provided_time = try_strptime(
            request.form['date'] + "T" + request.form['time'],
            "%Y-%m-%dT%H:%M"
        )
    if provided_time is None:
        session['last_error'] = "The headcount time was formatted " \
                                "improperly."
        return redirect(url_for('error'))
    current_time = datetime.datetime.now()
    # Copy the request arguments
    counts = dict(request.form)
    # Delete the ones that I don't need
    del (counts['date'])
    del (counts['time'])
    del (counts['submit'])
    if 'reverse-inputs' in counts.keys():
        del (counts['reverse-inputs'])
    provided_rooms = set(counts.keys())
    configured_rooms = set([room.name for room in app.config[
        'HC_CONFIG'].values()])
    if provided_rooms != configured_rooms:
        extraneous = provided_rooms - configured_rooms
        missing = configured_rooms - provided_rooms
        session['last_error'] = "You provided extraneous rooms %s and did " \
                                "not include required rooms %s." % \
                                (extraneous, missing)
        return redirect(url_for("error"))
    badkeys = []
    oversizekeys = []
    # Loop over all of the provided rooms
    for key, value in counts.items():
        # Value is actually a list, so just take the last item out of it
        value = value[-1:][0]
        # Interpret missing values as 0, as per [se.rit.edu #25]
        if value == '':
            value = '0'
            # Update the dictionary, fixes [se.rit.edu #95]
            counts[key] = [value]
        # If it's not numeric,
        if not value.isdigit():
            # Mark the key as bad
            badkeys.append(key)
        elif int(value) > app.config['HC_CONFIG'][key].max_occupancy:
            # If the value is larger than the value configured in the
            # config file, mark the key as too big
            oversizekeys.append(key)
    # If the length of the badkeys list is non-zero, throw back an error
    if len(badkeys) > 0:
        session['last_error'] = "Your request had non-numeric values for " \
                                "these rooms: " + str(badkeys)
        return redirect(url_for("error"))
    # If the length of the oversize keys list is non-zero, throw back an
    # error
    if len(oversizekeys) > 0:
        session['last_error'] = "The application isn't configured to " \
                                "allow that many people in these rooms: " \
                                "%s" % (str(oversizekeys),)
        return redirect(url_for("error"))
    # Get the requesting user from the database
    user = db.get_user_by_name(session['username'])
    # Give those arguments to the database
    db.add_headcount(user['id'], current_time, provided_time, counts)
    return redirect(url_for('show_main'))


@app.route("/main-edit", methods=['GET'])
@authenticated
def show_main_edit():
    db = get_db()
    now = datetime.datetime.now()
    rooms = [room for room in app.config["HC_CONFIG"].values()]
    rooms.sort(key=config_lexer.Room.sortkey)
    # Get the three newest counts from the database, sorted by the
    # user-provided time
    newest_counts = db.get_newest_counts_for_user(
        3,
        session['username'],
        hc_db.NewestSort.ENTERED_TIME
    )
    recent_counts = []
    for count in newest_counts:
        room_rows = db.get_roomdata_for_count_id(count['id'])
        # I couldn't think of a short, descriptive name for this variable.
        some_dict = {"id": count['id'], "date": count['entered_time'],
                     "counts": {}}
        for row in room_rows:
            some_dict["counts"][row['room']] = row['people_count']
        some_dict['counts'] = OrderedDict(
            sorted(some_dict['counts'].items(), key=sort_count_data)
        )
        recent_counts.append(some_dict)
    if is_admin(session['username']):
        buttons = [
            NavButton(url_for("show_admin"), "Administration"),
            NavButton(url_for("show_help"), "Help"),
            NavButton(url_for("logout"), "Log Out")
        ]
    else:
        buttons = [
            NavButton(url_for("show_help"), "Help"),
            NavButton(url_for("logout"), "Log Out")
        ]
    return render_template(
        "main-edit.html",
        buttons=buttons,
        rooms=rooms,
        recent_counts=recent_counts,
        datewhen=now.strftime("%Y-%m-%d"),
        timewhen=now.strftime("%H:%M")
    )


@app.route("/main-edit", methods=['POST'])
@authenticated
def submit_main_edit():
    db = get_db()

    # are we updating the headcounts or deleting them?
    if "delete" in request.form.keys():
        for key in request.form.keys():
            key_split = key.split("-")
            if len(key_split) < 2:
                continue
            if key_split[0] != "delete":
                continue
            if request.form.get(key) != "on":
                continue
            count_id = key_split[1]
            try:
                count_id = int(count_id)
                if not db.can_modify(session['username'], count_id):
                    session['last_error'] = "You cannot delete that headcount."
                    return redirect(url_for("error"))
                db.del_headcount(count_id)
            except ValueError:
                continue
    elif "save" in request.form.keys():
        updates = {}
        for key, val in request.form.items():
            key_split = key.split("-")
            if len(key_split) <= 1:
                continue
            count_id = key_split[1]
            try:
                count_id = int(count_id)
                if count_id not in updates.keys():
                    updates[count_id] = {
                        "submit_time": datetime.datetime.now(),
                        "entered_date": "",
                        "entered_time": "",
                        "rooms": {}
                    }
                if key_split[0] == "date":
                    updates[count_id]["entered_date"] = val
                elif key_split[0] == "time":
                    updates[count_id]["entered_time"] = val
                else:
                    updates[count_id]["rooms"][key_split[0]] = int(val)
            except ValueError:
                continue
        for key in updates.keys():
            if not db.can_modify(session['username'], key):
                session["last_error"] = "You cannot edit that headcount."
                return redirect(url_for("error"))
            t = try_strptime(
                updates[key]["entered_date"] + "T" +
                updates[key]["entered_time"],
                "%Y-%m-%dT%H:%M:%S"
            )
            if t is None:
                provided_time = try_strptime(
                    updates[key]["entered_date"] + "T" +
                    updates[key]["entered_time"],
                    "%Y-%m-%dT%H:%M"
                )
            if t is None:
                session['last_error'] = "The headcount time was formatted " \
                                        "improperly."
                return redirect(url_for('error'))
            updates[key]["entered_time"] = t
            db.edit_headcount(updates[key], key)
    return redirect(url_for("show_main_edit"))


def get_csv_logs(how_many_rows: int) -> str:
    """Get the logs from the database and convert them into CSV"""
    db = get_db()
    counts = db.get_newest_counts(how_many_rows, hc_db.NewestSort.SUBMIT_TIME)
    counts_as_string = ""
    for count in counts:
        username = db.get_user_by_id(count['user_id'])
        # Don't error out when there are headcounts by users who no longer exist
        if username is None:
            username = "(Deleted user; ID %s)" % (count['user_id'],)
        else:
            username = username['username']
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
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("show_help"), "Help"),
            NavButton(url_for("logout"), "Log Out"),
        ],
    )


@app.route("/admin", methods=['GET'])
@admin_authenticated
def show_admin():
    return render_admin_page("admin.html")


@app.route("/admin", methods=['POST'])
@admin_authenticated
def admin_update_preview():
    return user_management_handler("show_admin", "", False)


def avoid_lockouts():
    db = get_db()
    if db.count_admins()[0][0] <= 2:
        session['last_error'] = "You can't delete all of the administrators."
        return False
    return True


def user_management_handler(redir_page: str, new_users_field_name: str,
                            admins: bool):
    """The two admin editing pages are basically the same, except for some
    slightly different variable names. So, I rolled them into this function.
    :param redir_page: The page to redirect to upon success
    :param new_users_field_name: The name of the field containing new users
    :param admins: Are we adding/deleting administrators?
    """
    # Get a DB connection
    db = get_db()
    # The arguments should have a key "add" if the user clicked the "+" button
    if request.form.get("add") is not None:
        # In a well-formatted request, this is a comma-separated list
        new_users = request.form.get(new_users_field_name)
        new_users_l = new_users.split(",")
        add_user(new_users_l, admins)
        return redirect(url_for(redir_page))
    elif request.form.get("update-rows") is not None:
        # If necessary, update the row counts for the plain-text log viewer
        new_rows = int(request.form.get("rows"))
        if new_rows is not None and new_rows in allowed_row_counts:
            session['log_rows'] = new_rows
    elif request.form.get('delete') is not None:
        # The arguments should have a key "delete" if the user clicked the
        # trash bin
        # Copy the request, since we need to make changes
        args_copy = dict(request.form)
        # Delete this key, since we don't need it
        del args_copy["delete"]
        # If the request also has a new_admins key, delete that too
        if new_users_field_name in args_copy.keys():
            del args_copy[new_users_field_name]
        for user in args_copy.keys():
            if validate_username(user) and db.does_user_exist(user):
                # If we're deleting admins, avoid locking everybody out
                if admins:
                    if avoid_lockouts() and is_admin(user):
                        db.del_user(user)
                    else:
                        return redirect(url_for('error'))
                else:
                    # Otherwise, just delete the user
                    if not is_admin(user):
                        db.del_user(user)
                    else:
                        session["last_error"] = "%s is not an administrator." % \
                                                (user,)
            else:
                # If it wasn't a valid username or the user wasn't in the
                # database,
                # If the user wasn't in the database, no error will be set,
                # so set it
                if "last_error" not in session.keys():
                    session['last_error'] = "That user doesn't exist."
                # Redirect to the error page
                return redirect(url_for('error'))
        return redirect(url_for(redir_page))
    return redirect(url_for(redir_page))


@app.route("/admin/edit-admins", methods=['GET'])
@admin_authenticated
def show_admin_edit_admins():
    return render_admin_page("admin-ea.html")


@app.route("/admin/edit-admins", methods=['POST'])
@admin_authenticated
def admin_edit_admins():
    return user_management_handler("show_admin_edit_admins", "new_admins", True)


@app.route("/admin/edit-users", methods=['GET'])
@admin_authenticated
def show_admin_edit_users():
    return render_admin_page("admin-eu.html")


@app.route("/admin/edit-users", methods=['POST'])
@admin_authenticated
def admin_edit_users():
    return user_management_handler("show_admin_edit_users", "new_users", False)


@app.route("/logout")
def logout():
    if 'username' in session.keys():
        del (session['username'])
    if not app.config["DISABLE_AUTH"]:
        return redirect(url_for("login") + "?slo")
    else:
        return redirect(url_for('index'))


@app.route("/help")
def show_help():
    if 'username' in session.keys() and is_admin(session['username']):
        buttons = [
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("show_admin"), "Administration")
        ]
    elif 'username' in session.keys():
        buttons = [
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_main"), "Main"),
        ]
    else:
        buttons = [
            NavButton(url_for("index"), "Home")
        ]
    return render_template(
        "help.html",
        buttons=buttons
    )


@app.route("/error")
def error():
    if "last_error" in session.keys():
        error_msg = session["last_error"]
        del (session["last_error"])
    else:
        error_msg = "An unspecified error occurred."
    if 'username' in session.keys():
        buttons = [
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("show_help"), "Help")
        ]
    else:
        buttons = [
            NavButton(url_for("login") + "?sso", "Log In"),
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("show_help"), "Help")
        ]
    return render_template(
        'error.html',
        message=error_msg,
        buttons=buttons
    )


def main():
    app.config["HC_CONFIG"] = config_lexer.read_configuration()


def main_dbg():
    app.config["HC_CONFIG"] = config_lexer.read_configuration()
    app.run(debug=True)


main()
# main_dbg()
