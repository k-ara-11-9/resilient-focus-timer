-- Migration to add Users and Ownership to Sessions and Interruptions

-- WARNING: The original database schema (from migrate.py) contained a stub 'User' table 
-- with only a 'UserID' column. If that table exists and is unused, you should drop it first:
DROP TABLE IF EXISTS User;

-- 1. Create the new User table
CREATE TABLE User (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

-- 2. Add user_id to Session
-- SAFE FOR EXISTING DATA: This will succeed on an existing database. 
-- Existing rows will have user_id = NULL.
ALTER TABLE Session ADD COLUMN user_id INTEGER REFERENCES User(id);

-- 3. Add user_id to Interruption
-- SAFE FOR EXISTING DATA: This will succeed on an existing database.
-- Existing rows will have user_id = NULL.
ALTER TABLE Interruption ADD COLUMN user_id INTEGER REFERENCES User(id);
