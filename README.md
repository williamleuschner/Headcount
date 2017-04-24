# Headcount

Headcount is a web application for [RIT](https://rit.edu)'s
[Software Engineering](https://se.rit.edu) department that allows labbies to 
take headcounts in the team rooms and the Co-Lab. It is built using Python 3,
 Flask, and uWSGI. It's also designed to work on OpenBSD with [Reyk Floeter's 
`httpd`](https://gitub.com/reyk/httpd) by default. 
 
## Installation
Installation instructions are only provided for OpenBSD. It *is* just a uWSGI 
app, so installing it *should* be easy on other platforms.

1. Create the user `_headcount` and group `_headcount`. Set `_headcount`'s 
home directory to `/usr/local/_headcount`
2. Install:
    * `python%3.6`
    * `py3-pip`
    * `py3-virtualenv`
    * `xmlsec`
3. Change to the user `_headcount`
4. Create a Python virtualenv in `/usr/local/_headcount`. It should be called
 `hc-venv`. Activate the virtualenv.
5. Use `pip` to install the `requirements.txt` file.
6. Clone [github.com/pallets/flask.git](https://github.com/pallets/flask.git)
 and run `setup.py install`.
7. `cd` back to `/usr/local/_headcount/Headcount/src` and initialize the 
application's database by executing `FLASK_APP=headcount.py flask initdb`.
8. Add the primary administrator's username to the database by executing
`FLASK_APP=headcount.py flask add_admin $ADMIN_NAME`
9. Change back to `root`
10. Copy `config/headcount.rc` to `/etc/rc.d/headcount`

Here is a suggested `httpd` configuration:

```
ext_addr="egress"

server "headcount.se.rit.edu" {
    listen on $ext_addr port 80

    location "/.well-known/acme-challenge/*" {
        root "/acme"
        root strip 2
    }

    location "/*" {
        block return 301 "https://$SERVER_NAME$REQUEST_URI"
    }
}

server "headcount.se.rit.edu" {
    listen on $ext_addr tls port 443

    tls certificate "/etc/ssl/acme/headcount.se.rit.edu.fullchain.pem"
    tls key "/etc/ssl/acme/private/headcount.se.rit.edu.key"

    location "/" {
        block return 301 "https://$SERVER_NAME/index"
    }
    location "/*" {
        fastcgi socket "/run/headcount.sock"
    }
}
```

Enjoy!