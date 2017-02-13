#!/bin/ksh

# Install Headcount on an OpenBSD system
# Must be run as root

# First, create a user and group to run the service as
groupadd _headcount
useradd -b /usr/local/ -d _headcount -m -s /bin/false _headcount 

# Install Python 3, Git, and Pip
# As of 6.0, the default packages only include python 3.4 with pip, so that's what we use
pkg_add python%3.4
pkg_add git
pkg_add py3-pip

# Clone the repo into _headcount's home directory
# Note that this breaks unless you're me, since I haven't set up Git properly yet.
# TODO: un-break git
cd /usr/local/_headcount
su _headcount git clone ssh://william@peanut.se.rit.edu:/home/william/Git/Headcount
chown -R _headcount:_headcount Headcount

# Install virtualenv
pip3.4 install virtualenv
virtualenv hc-venv
chown -R _headcount:_headcount hc-venv

# Install required python modules
. hc-venv/bin/activate
pip3 install -r requirements.txt

# Copy uWSGI configs into place

