#!/bin/ksh

# Install Headcount on an OpenBSD system
# Must be run as root

# First, create a user and group to run the service as
groupadd _headcount
useradd -b /usr/local/ -d _headcount -m -s /bin/ksh _headcount

# Install Python 3, Git, and Pip
# As of 6.1, the default packages only include python 3.4 with pip, so that's
# what we use
pkg_add python%3.6
pkg_add git
pkg_add py3-pip
pkg_add xmlsec

# Clone the repo into _headcount's home directory
cd /usr/local/_headcount
su _headcount git clone ssh://git@peanut.se.rit.edu:/home/git/Headcount
chown -R _headcount:_headcount Headcount

# Install virtualenv
pip3.6 install virtualenv
virtualenv-3 hc-venv
chown -R _headcount:_headcount hc-venv

# Install required python modules
# Also, install Flask from source because the one from pip has a heart attack
# when you try to run `FLASK_APP=headcount.py flask initdb`
su _headcount <<'EOF'
. hc-venv/bin/activate
pip3 install -r Headcount/requirements.txt
git clone https://github.com/pallets/flask.git
cd flask
python3 setup.py install
cd /usr/local/_headcount/Headcount/src
FLASK_APP=headcount.py
read -p "RIT Username of primary administrator: " ADMIN_NAME
flask initdb
flask add_admin "$ADMIN_NAME"
EOF

# Copy initscript into /etc/rc.d
cp src/headcount.rc /etc/rc.d/headcount

# Set _headcount's shell to /usr/bin/false, since that user should not be able
# to run any commands
chpass -s /usr/bin/false _headcount

echo "You may want to examine the httpd configuration located in httpd.example."
echo "You should also add headcount to the list of startup services in a"
echo "position after httpd."
