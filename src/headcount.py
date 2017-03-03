# Headcount.py
# A Server-Side Python Application for Labbies Taking Headcounts in SE
# Classrooms
# Author: William Leuschner
# File Creation Date: 2017-02-01
# Last Modified Date: 2017-02-21

import os

from flask import Flask, request, render_template, redirect, session, \
    make_response, url_for

from urllib.parse import urlparse

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

import config_lexer
import hc_db

from collections import namedtuple

app = Flask(__name__)

app.config['SAML_PATH'] = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'saml'
)
app.config['DATABASE'] = hc_db.HCDB()
#################################
#     WARNING: SHARP EDGES!     #
#   SET TO FALSE IN PRODUCTION  #
#   I think it's obvious why.   #
#################################
app.config['DISABLE_AUTH'] = True

NavButton = namedtuple("NavButton", "location name")


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


@app.route("/", methods=['GET', 'POST'])
def index():
    req = prepare_flask_request(request)
    auth = init_saml_auth(req)
    errors = []
    not_auth_warn = False
    success_slo = False
    attributes = False
    paint_logout = False

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

    return render_template("index.html")


@app.route("/main")
def show_main():
    status = ""
    return render_template(
        "main.html",
        status=status,
        buttons=[
            NavButton(url_for("logout"), "Log Out"),
            NavButton(url_for("show_admin"), "Administration"),
            NavButton(url_for("help"), "Help")
        ]
    )


@app.route("/admin")
def show_admin():
    users = []
    admins = []
    return render_template(
        "admin.html",
        users=users,
        admins=admins
    )


@app.route("/admin/edit-admins")
def show_admin_edit_admins():
    users = []
    admins = []
    return render_template(
        "admin-ea.html",
        users=users,
        admins=admins
    )


@app.route("/admin/edit-users")
def show_admin_edit_users():
    users = []
    admins = []
    return render_template(
        "admin-eu.html",
        users=users,
        admins=admins
    )


@app.route("/logout")
def logout():
    return "This is broken."


@app.route("/help")
def help():
    return "This is broken."


def main():
    config = config_lexer.read_configuration()

main()
