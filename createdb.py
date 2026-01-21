import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# Players
c.execute("""
CREATE TABLE IF NOT EXISTS players(
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT UNIQUE,
team TEXT,
matches INTEGER DEFAULT 0,
points INTEGER DEFAULT 0,
aces INTEGER DEFAULT 0,
attacks INTEGER DEFAULT 0,
blocks INTEGER DEFAULT 0,
digs INTEGER DEFAULT 0,
errors INTEGER DEFAULT 0,
mvp INTEGER DEFAULT 0
)
""")

# Matches
c.execute("""
CREATE TABLE IF NOT EXISTS matches(
id INTEGER PRIMARY KEY AUTOINCREMENT,
teamA TEXT,
teamB TEXT,
winner TEXT,
date TEXT
)
""")

# Match Stats
c.execute("""
CREATE TABLE IF NOT EXISTS match_stats(
id INTEGER PRIMARY KEY AUTOINCREMENT,
match_id INTEGER,
player TEXT,
team TEXT,
points INTEGER,
aces INTEGER,
attacks INTEGER,
blocks INTEGER,
digs INTEGER,
errors INTEGER
)
""")

# Tournament
c.execute("""
CREATE TABLE IF NOT EXISTS tournaments(
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT
)
""")

# Fixtures
c.execute("""
CREATE TABLE IF NOT EXISTS fixtures(
id INTEGER PRIMARY KEY AUTOINCREMENT,
tournament_id INTEGER,
teamA TEXT,
teamB TEXT,
winner TEXT
)
""")

conn.commit()
conn.close()

print("Database Ready")
