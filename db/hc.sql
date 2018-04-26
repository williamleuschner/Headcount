CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY NOT NULL,
    username CHAR(7) UNIQUE NOT NULL,
    is_admin BOOLEAN NOT NULL CHECK(is_admin IN (0,1))
);
CREATE TABLE IF NOT EXISTS headcounts (
    id INTEGER PRIMARY KEY NOT NULL,
    user_id INTEGER NOT NULL,
    submit_time DATETIME NOT NULL,
    entered_time DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS room_data (
    id INTEGER PRIMARY KEY NOT NULL,
    room CHAR(20) NOT NULL,
    people_count INT NOT NULL,
    count_id INTEGER NOT NULL,
    FOREIGN KEY(count_id) REFERENCES headcounts(id)
);