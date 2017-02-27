# The database bridge class for Headcount
# Allows abstraction of the database layer so that if SQLite turns out to be too
# "lite", it can be replaced with a more powerful alternative
# Author: William Leuschner
# Creation Date: 2017-02-22
# Last Modified Date: 2017-02-22

import sqlite3
import datetime

# Where's the file the DB is in?
DB_FILE_NAME = "../db/hc.db"


class HCDB:
    """Headcount Database Interface"""
    # Add a headcount
    ADD_HEADCOUNT_Q = \
        "INSERT INTO headcounts (user_id, submit_time, entered_time) VALUES (?,?,?)"
    # Add a room to the headcount
    ADD_HC_ROOMS_Q = \
        "INSERT INTO room_data (room, people_count, room_id) VALUES (?,?,?)"
    # Add a user
    ADD_USER_Q = "INSERT INTO users (username, is_admin) VALUES (?,?)"
    # Get all of a user's data
    GET_USER_Q = "SELECT (id, username, is_admin) FROM users WHERE username=?"
    # Delete a user by ID
    DEL_USER_Q = "DELETE FROM users WHERE id=?"

    def __init__(self):
        """Create a new instance of the HCDB"""
        self.db = sqlite3.connect(DB_FILE_NAME)
        self.cursor = self.db.cursor()
        self.filename = DB_FILE_NAME

    def __repr__(self) -> str:
        """Turn this HCDB into a semi-meaningful string"""
        return "sqlite3: %s" % self.filename

    def _executeone(self, query: str, *args) -> tuple:
        """Private method to execute a query and return one row of results"""
        r = self.cursor.execute(query, *args)
        return r.fetchone()

    def _executemany(self, query: str, arglist: list) -> tuple:
        """Private method to execute a query with many inputs, and return one
        row of results"""
        r = self.cursor.executemany(query, arglist)
        return r.fetchone()

    def _execute(self, query: str, *args) -> sqlite3.Cursor:
        """Private method to execute a query
        :param query A SQL query to execute on the database"""
        return self.cursor.execute(query, *args)

    def add_headcount(
            self,
            user_id: str,
            submit_time: datetime.datetime,
            entered_time: datetime.datetime,
            counts: dict
    ):
        """Add a new headcount to the database
        :param user_id The username of the submitter
        :param submit_time When the user actually submitted the count
        :param entered_time When the user *said* they submitted the count
        :param counts A dictionary of the rooms to add counts to"""
        hc = self._execute(
            HCDB.ADD_HEADCOUNT_Q,
            (user_id, submit_time, entered_time)
        )
        self._executemany(
            HCDB.ADD_HC_ROOMS_Q,
            # This list comprehension converts the dictionary argument into a
            # list of tuples, but with a third element (the headcount ID)
            [(rm, c, hc.lastrowid) for rm, c in counts.items()]
        )

    def add_user(self, username, is_admin=False):
        """Add a new user to the users table"""
        self._execute(HCDB.ADD_USER_Q, (username, 1 if is_admin else 0))

    def del_user(self, username):
        """Delete a user from the users table"""
        u = self._executeone(HCDB.GET_USER_Q, (username))
        self._execute(HCDB.DEL_USER_Q, (u[0],))

    def get_user(self, username):
        """Return the user, if one exists with the provided username"""
        return self._executeone(HCDB.GET_USER_Q, (username,))
