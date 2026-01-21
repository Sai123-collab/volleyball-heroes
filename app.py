from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os
import json

# Firebase
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
app.secret_key = "volleyball"


# ---------------- FIREBASE INIT (RENDER SAFE) ----------------

firebase_key = os.environ.get("FIREBASE_KEY")

if not firebase_key:
    raise ValueError("FIREBASE_KEY environment variable not set")

firebase_json = json.loads(firebase_key)

cred = credentials.Certificate(firebase_json)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://volleyball-heroes-live-default-rtdb.firebaseio.com/'
})

# ⚠ Replace with YOUR realtime database URL


# ---------------- HOME ----------------

@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        session["match_type"] = request.form["match_type"]

        if session["match_type"] == "set":
            session["sets"] = int(request.form["sets"])
            session["set_points"] = int(request.form["points"])
        else:
            session["set_points"] = 15

        return redirect("/teams")

    return render_template("index.html")


# ---------------- TEAMS ----------------

@app.route("/teams", methods=["GET", "POST"])
def teams():

    if request.method == "POST":

        session["teamA"] = request.form["teamA"]
        session["teamB"] = request.form["teamB"]

        return redirect("/players")

    return render_template("teams.html")


# ---------------- PLAYERS ----------------

@app.route("/players", methods=["GET", "POST"])
def players():

    if request.method == "POST":

        session["teamA_players"] = request.form.getlist("teamA[]")
        session["teamB_players"] = request.form.getlist("teamB[]")

        # INITIAL MATCH VALUES
        session["scoreA"] = 0
        session["scoreB"] = 0
        session["setA"] = 0
        session["setB"] = 0
        session["current_set"] = 1

        # SERVE START
        session["serve"] = "A"

        # PLAYER STATS
        session["stats"] = {}

        for p in session["teamA_players"] + session["teamB_players"]:
            session["stats"][p] = {
                "points": 0,
                "aces": 0,
                "attacks": 0,
                "blocks": 0,
                "digs": 0,
                "errors": 0
            }

        return redirect("/scoreboard")

    return render_template("players.html")


# ---------------- LIVE MATCH ----------------

@app.route("/scoreboard", methods=["GET", "POST"])
def scoreboard():

    winner = None

    if request.method == "POST":

        player = request.form.get("player")
        team = request.form.get("team")
        action = request.form.get("action")

        print("TEAM:", team, "PLAYER:", player, "ACTION:", action)

        # -------- TEAM SCORE --------

        if action != "error":

            if team == "A":
                session["scoreA"] += 1

            elif team == "B":
                session["scoreB"] += 1

            session["stats"][player]["points"] += 1

            # Update serve
            session["serve"] = team

        # -------- PLAYER STATS --------

        if action == "ace":
            session["stats"][player]["aces"] += 1

        elif action == "attack":
            session["stats"][player]["attacks"] += 1

        elif action == "block":
            session["stats"][player]["blocks"] += 1

        elif action == "dig":
            session["stats"][player]["digs"] += 1

        elif action == "error":
            session["stats"][player]["errors"] += 1

        p = session["set_points"]

        # -------- SINGLE MATCH --------

        if session["match_type"] == "single":

            if (session["scoreA"] >= 15 or session["scoreB"] >= 15) and \
               abs(session["scoreA"] - session["scoreB"]) >= 2:

                winner = session["teamA"] if session["scoreA"] > session["scoreB"] else session["teamB"]
                save_match(winner)

        # -------- SET MATCH --------

        else:

            if (session["scoreA"] >= p or session["scoreB"] >= p) and \
               abs(session["scoreA"] - session["scoreB"]) >= 2:

                if session["scoreA"] > session["scoreB"]:
                    session["setA"] += 1
                else:
                    session["setB"] += 1

                # Reset set scores
                session["scoreA"] = 0
                session["scoreB"] = 0
                session["current_set"] += 1

            win_sets = session["sets"] // 2 + 1

            if session["setA"] == win_sets:
                winner = session["teamA"]
                save_match(winner)

            elif session["setB"] == win_sets:
                winner = session["teamB"]
                save_match(winner)

        # -------- FIREBASE LIVE UPDATE --------

        live_ref = db.reference("live_match")

        live_ref.set({

            "teamA": session["teamA"],
            "teamB": session["teamB"],

            "scoreA": session["scoreA"],
            "scoreB": session["scoreB"],

            "setA": session.get("setA", 0),
            "setB": session.get("setB", 0),

            "current_set": session.get("current_set", 1),

            "serve": session["teamA"] if session["serve"] == "A" else session["teamB"]

        })

    return render_template("scoreboard.html", winner=winner)


# ---------------- SAVE MATCH + MVP ----------------

def save_match(winner):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    date = datetime.now().strftime("%d-%m-%Y %H:%M")

    c.execute(
        "INSERT INTO matches(teamA,teamB,winner,date) VALUES(?,?,?,?)",
        (session["teamA"], session["teamB"], winner, date)
    )

    match_id = c.lastrowid

    best_score = -999
    mvp = ""

    for player, data in session["stats"].items():

        team = session["teamA"] if player in session["teamA_players"] else session["teamB"]

        score = (data["points"] +
                 data["aces"] * 2 +
                 data["attacks"] * 2 +
                 data["blocks"] * 2 +
                 data["digs"] -
                 data["errors"])

        if score > best_score:
            best_score = score
            mvp = player

        c.execute("""
        INSERT INTO match_stats
        (match_id,player,team,points,aces,attacks,blocks,digs,errors)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (match_id, player, team,
              data["points"], data["aces"], data["attacks"],
              data["blocks"], data["digs"], data["errors"]))

        c.execute("INSERT OR IGNORE INTO players(name,team) VALUES(?,?)", (player, team))

        c.execute("""
        UPDATE players SET
        matches = matches + 1,
        points = points + ?,
        aces = aces + ?,
        attacks = attacks + ?,
        blocks = blocks + ?,
        digs = digs + ?,
        errors = errors + ?
        WHERE name = ?
        """, (data["points"], data["aces"], data["attacks"],
              data["blocks"], data["digs"], data["errors"], player))

    c.execute("UPDATE players SET mvp = mvp + 1 WHERE name=?", (mvp,))

    conn.commit()
    conn.close()


# ---------------- HISTORY ----------------

@app.route("/history")
def history():

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM matches ORDER BY id DESC")
    matches = c.fetchall()

    conn.close()

    return render_template("history.html", matches=matches)


# ---------------- LEADERBOARD ----------------

@app.route("/leaderboard")
def leaderboard():

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT name,points,mvp FROM players ORDER BY points DESC")
    players = c.fetchall()

    conn.close()

    return render_template("leaderboard.html", players=players)


# ---------------- PLAYER PROFILE ----------------

@app.route("/player/<name>")
def player_profile(name):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM players WHERE name=?", (name,))
    player = c.fetchone()

    conn.close()

    return render_template("player_profile.html", player=player)


# ---------------- PDF SCORECARD ----------------

@app.route("/pdf/<int:id>")
def pdf(id):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM match_stats WHERE match_id=?", (id,))
    stats = c.fetchall()

    conn.close()

    file = f"scorecard_{id}.pdf"

    doc = SimpleDocTemplate(file)
    styles = getSampleStyleSheet()
    story = []

    for s in stats:
        story.append(Paragraph(str(s), styles["BodyText"]))

    doc.build(story)

    return f"PDF Created Successfully: {file}"


# ---------------- PUBLIC LIVE VIEW ----------------

@app.route("/live")
def live():
    return render_template("public_view.html")


# ---------------- RESET ----------------

@app.route("/reset")
def reset():
    session.clear()
    return redirect("/")


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run()
