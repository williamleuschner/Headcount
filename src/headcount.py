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

import config_lexer
import hc_db
import datetime
import re

from collections import namedtuple, OrderedDict

app = Flask(__name__)

app.config['SAML_PATH'] = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'saml'
)
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
        return redirect(url_for('show_main'))


# Needs authentication code
@app.route("/main")
def show_main():
    # If there is no submit argument, just render the page
    if request.args.get("submit", "") == "":
        db = get_db()
        now = datetime.datetime.now()
        rooms = [room for room in app.config["HC_CONFIG"]]
        rooms.sort(key=config_lexer.Room.sortkey)
        # Get the three newest counts from the database, sorted by the
        # user-provided time
        newest_counts = db.get_newest_counts(3, hc_db.NewestSort.ENTERED_TIME).fetchall()
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
        user = db.get_user("wel2138")
        # Give those arguments to the database
        db.add_headcount(user['id'], current_time, provided_time, counts)
        return redirect(url_for('show_main'))


def render_admin_page(template_name: str):
    """Render an admin page, since this code gets repeated three times"""
    db = get_db()
    usernames = [u['username'] for u in db.get_all_users(False)]
    adminnames = [a['username'] for a in db.get_all_users(True)]
    return render_template(
        template_name,
        users=usernames,
        admins=adminnames,
        logs="",
        buttons=[
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_main"), "Main"),
            NavButton(url_for("help"), "Help")
        ],
    )


@app.route("/admin")
def show_admin():
    return render_admin_page("admin.html")


@app.route("/admin/edit-admins")
def show_admin_edit_admins():
    db = get_db()
    if request.args.get("add") is not None:
        print("Adding admins...")
        new_admins = request.args.get("new_admins")
        if new_admins is not None:
            new_admins_l = new_admins.split(",")
            print("\t", new_admins_l)
            for admin in new_admins_l:
                print("\tAdding...")
                if validate_username(admin):
                    print("\t\tAdded!")
                    db.add_user(admin, is_admin=True)
                else:
                    print("\t\tInvalid format.")
        return redirect(url_for('show_admin_edit_admins'))
    elif request.args.get('delete') is not None:
        print("Deleting admins...")
        if len(request.args) >= 2:
            print("\tThere were enough arguments")
            args_copy = dict(request.args)
            if "delete" in args_copy.keys():
                del args_copy["delete"]
            if "new_admins" in args_copy.keys():
                del args_copy["new_admins"]
            for admin in args_copy.keys():
                print("\tTesting %s..." % admin)
                if validate_username(admin) and db.does_user_exist(admin):
                    print("\t\tDeleted!")
                    db.del_user(admin)
                else:
                    print("\t\tInvalid username.")
        return redirect(url_for('show_admin_edit_admins'))
    else:
        return render_admin_page("admin-ea.html")


@app.route("/admin/edit-users")
def show_admin_edit_users():
    return render_admin_page("admin-eu.html")


@app.route("/logout")
def logout():
    if not app.config["DISABLE_AUTH"]:
        pass
    else:
        return redirect(url_for('index'))


@app.route("/help")
def help():
    return "This is broken."


def main():
    app.config["HC_CONFIG"] = config_lexer.read_configuration()

main()
