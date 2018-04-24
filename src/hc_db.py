# The database bridge class for Headcount
# Allows abstraction of the database layer so that if SQLite turns out to be too
# "lite", it can be replaced with a more powerful alternative
# Author: William Leuschner
# Creation Date: 2017-02-22

import datetime
import sqlite3
from enum import Enum
from typing import Iterable


class NewestSort(Enum):
    SUBMIT_TIME = "submit_time"
    ENTERED_TIME = "entered_time"


class HCDB:
    """Headcount Database Interface"""
    # Add a headcount
    ADD_HEADCOUNT_Q = \
        "INSERT INTO headcounts (user_id, submit_time, entered_time) VALUES " \
        "(?,?,?);"
    # Modify an existing headcount
    EDIT_HEADCOUNT_Q = \
        "UPDATE headcounts SET submit_time=?, entered_time=? WHERE id=?;"
    # Add a room to the headcount
    ADD_HC_ROOMS_Q = \
        "INSERT INTO room_data (room, people_count, count_id) VALUES (?,?,?);"
    # Edit the number of people in a room
    EDIT_HC_ROOM_Q = \
        "UPDATE room_data SET people_count=? WHERE room=? AND count_id=?;"
    # Add a user
    ADD_USER_Q = "INSERT INTO users (username, is_admin) VALUES (?,?);"
    # Get all of a user's data
    GET_USER_Q = "SELECT id, username, is_admin FROM users WHERE username=?;"
    # Get all of a user's data, by ID
    GET_USER_BY_ID_Q = "SELECT id, username, is_admin FROM users WHERE " \
                       "id=?;"
    # Select users where is_admin is true or false
    GET_USER_BY_ADMIN_Q = "SELECT id, username FROM users WHERE is_admin=?;"
    # Delete a user by ID
    DEL_USER_Q = "DELETE FROM users WHERE id=?;"
    # Get the most recent ? headcounts
    NEWEST_COUNTS_Q = "SELECT id, user_id, submit_time, entered_time FROM " \
                      "headcounts ORDER BY %s DESC LIMIT ?;"
    NEWEST_COUNTS_USER_Q = "SELECT h.id, h.user_id, h.submit_time, " \
                           "h.entered_time FROM headcounts as h, " \
                           "users as u WHERE h.user_id = u.id AND u.username " \
                           "= ? ORDER BY %s DESC LIMIT ?;"
    # Get the room data for a given headcount ID
    ROOMDATA_Q = "SELECT id, room, people_count FROM room_data WHERE " \
                 "count_id=? ORDER BY room;"
    NUMADMINS_Q = "SELECT COUNT(username) FROM users WHERE is_admin=1;"

    def __init__(self, filename):
        """Create a new instance of the HCDB connector"""
        self.db = sqlite3.connect(filename)
        self.db.row_factory = sqlite3.Row
        self.cursor = self.db.cursor()
        self.filename = filename

    def __repr__(self) -> str:
        """Turn this HCDB into a semi-meaningful string"""
        return "sqlite3: %s" % self.filename

    def _executeone(self, query: str, *args) -> tuple:
        """Private method to execute a query and return one row of results"""
        r = self.cursor.execute(query, *args)
        return r.fetchone()

    def _executemany(self, query: str, arglist: Iterable) -> tuple:
        """Private method to execute a query with many inputs, and return one
        row of results"""
        r = self.cursor.executemany(query, arglist)
        return r.fetchone()

    def _execute(self, query: str, *args) -> sqlite3.Cursor:
        """Private method to execute a query
        :param query A SQL query to execute on the database"""
        return self.cursor.execute(query, *args)

    def initialize(self, schema_file):
        """Use the given schema file object to initialize the database.
        :param schema_file A file object that is read-enabled on the desired
                           schema file"""
        self.db.cursor().executescript(schema_file.read())
        self.db.commit()

    def add_headcount(
            self,
            user_id: int,
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
            [
                (room, int(count[0]), hc.lastrowid) \
                for room, count in counts.items()
            ]
        )
        self.db.commit()

    def edit_headcount(self, newdata: dict, id: int):
        """Modify the data for the headcount with the specified ID using the
        data in newdata. newdata must have the following structure:
            {
                "submit_time": "2018-04-19 12:26:00",
                "entered_time": "2018-04-19 13:00:00",
                "rooms": {
                    "1564": 1,
                    ...
                }
            }
        :param newdata: The new data for the headcount
        :param id: The ID of the headcount to modify"""
        self._execute(HCDB.EDIT_HC_ROOM_Q, (newdata['submit_time'], newdata[
            'entered_time'], id))
        for room, people in newdata['rooms'].iteritems():
            self._execute(HCDB.EDIT_HC_ROOM_Q, (people, room, id))

    def add_user(self, username, is_admin=False):
        """Add a new user to the users table"""
        self._execute(HCDB.ADD_USER_Q, (username, 1 if is_admin else 0))
        self.db.commit()

    def del_user(self, username):
        """Delete a user from the users table"""
        u = self._executeone(HCDB.GET_USER_Q, (username,))
        self._execute(HCDB.DEL_USER_Q, (u[0],))
        self.db.commit()

    def get_user_by_name(self, username):
        """Return the user, if one exists with the provided username"""
        return self._executeone(HCDB.GET_USER_Q, (username,))

    def get_user_by_id(self, user_id):
        """Return the user, if one exists, with the provided ID"""
        return self._executeone(HCDB.GET_USER_BY_ID_Q, (user_id,))

    def does_user_exist(self, username):
        """Returns True if that username is in the database, False if not."""
        return True if len(self._execute(HCDB.GET_USER_Q, (username,))
                           .fetchall()) > 0 else False

    def get_all_users(self, filter_by_admin: bool):
        """Get all of the users from the database, optionally filtering by
        admin status.
        :param filter_by_admin Set to True to only fetch admins, set to False to
                               only fetch non-admins."""
        if filter_by_admin is True:
            return self._execute(HCDB.GET_USER_BY_ADMIN_Q, (1,)).fetchall()
        elif filter_by_admin is False:
            return self._execute(HCDB.GET_USER_BY_ADMIN_Q, (0,)).fetchall()

    def get_newest_counts(self, how_many: int, sort: NewestSort):
        """Get n of the most recent headcounts
        :param how_many How many counts should be gotten?
        :param sort Sort newest by the time the user gave or the time the query
                    ran?"""
        # This only looks like a SQL injection. `sort' is an enum, and both
        # values of the enum are SQL-safe
        return self._execute(HCDB.NEWEST_COUNTS_Q % (sort.value,),
                             (how_many,)).fetchall()

    def get_newest_counts_for_user(self, how_many: int, for_whom: str, sort:
    NewestSort):
        """Get n of the most recent headcounts for a specific user.
        :param how_many How many counts should be retrieved?
        :param for_whom The username of the user to get counts for.
        :param sort Sort headcounts by the time the user gave, or the time 
                    the query ran?"""
        return self._execute(HCDB.NEWEST_COUNTS_USER_Q % (sort.value,),
                             (for_whom, how_many)).fetchall()

    def get_roomdata_for_count_id(self, count_id: int):
        """Get the per-room headcounts for a given count ID
        :param count_id The associated headcount ID to get data for"""
        return self._execute(HCDB.ROOMDATA_Q, (count_id,))

    def count_admins(self):
        """Return the current number of administrators."""
        return self._execute(HCDB.NUMADMINS_Q).fetchall()

    def close(self):
        """Closes the database connection"""
        self.db.close()
