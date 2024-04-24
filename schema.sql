DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS tracks;
DROP TABLE IF EXISTS artist_pages;
DROP TABLE IF EXISTS spotifytracks;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    album TEXT,
    name TEXT NOT NULL,
    genre TEXT,
    user_id INTEGER,
    file_path TEXT,
    image_url TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    rating INTEGER NOT NULL,
    user_id INTEGER,
    track_id INTEGER,
    track_type TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (track_id) REFERENCES tracks (id)
);

CREATE TABLE artist_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL,
    description TEXT,
    genre TEXT,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE spotifytracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    image_url TEXT
);

