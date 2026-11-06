from flask import Flask, render_template, request, redirect, url_for, flash
import csv, os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = "campus-event-demo-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVENTS_FILE = os.path.join(DATA_DIR, "events.csv")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.csv")
REG_FILE = os.path.join(DATA_DIR, "registrations.csv")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.csv")
CHART_FILE = os.path.join(BASE_DIR, "static", "participation.png")

os.makedirs(DATA_DIR, exist_ok=True)

def create_file(path, headers):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

create_file(EVENTS_FILE, ["event_id", "name", "date", "venue", "max_participants"])
create_file(STUDENTS_FILE, ["student_id", "name", "email", "department"])
create_file(REG_FILE, ["student_id", "event_id"])
create_file(FEEDBACK_FILE, ["student_id", "event_id", "rating"])

class Event:
    def __init__(self, event_id, name, date, venue, max_participants):
        self.event_id = event_id
        self.name = name
        self.date = date
        self.venue = venue
        self.max_participants = int(max_participants)

class Student:
    def __init__(self, student_id, name, email, department):
        self.student_id = student_id
        self.name = name
        self.email = email
        self.department = department

class Registration:
    def __init__(self, student_id, event_id):
        self.student_id = student_id
        self.event_id = event_id

def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_rows(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def participant_count(event_id):
    return sum(1 for r in read_rows(REG_FILE) if r["event_id"] == event_id)

def make_chart():
    events = read_rows(EVENTS_FILE)
    regs = read_rows(REG_FILE)
    names, counts = [], []
    for event in events:
        names.append(event["name"])
        counts.append(sum(1 for r in regs if r["event_id"] == event["event_id"]))
    plt.figure(figsize=(7, 3.5))
    plt.bar(names, counts)
    plt.title("Event-wise Participation")
    plt.xlabel("Events")
    plt.ylabel("Number of Students")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_FILE)
    plt.close()

@app.route("/", methods=["GET"])
def home():
    events = read_rows(EVENTS_FILE)
    registrations = read_rows(REG_FILE)
    students = read_rows(STUDENTS_FILE)
    feedback = read_rows(FEEDBACK_FILE)
    for e in events:
        e["registered"] = sum(1 for r in registrations if r["event_id"] == e["event_id"])
        e["seats_left"] = max(0, int(e["max_participants"]) - e["registered"])
    average = round(sum(int(f["rating"]) for f in feedback) / len(feedback), 2) if feedback else 0
    make_chart()
    return render_template("index.html", events=events, students=students,
                           registrations=registrations, feedback_count=len(feedback),
                           average=average, search_result=None)

@app.route("/add_event", methods=["POST"])
def add_event():
    event_id = request.form["event_id"].strip()
    if any(e["event_id"] == event_id for e in read_rows(EVENTS_FILE)):
        flash("This Event ID already exists.", "error")
        return redirect(url_for("home"))
    event = Event(event_id, request.form["name"].strip(), request.form["date"],
                  request.form["venue"].strip(), request.form["max_participants"])
    with open(EVENTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([event.event_id, event.name, event.date, event.venue, event.max_participants])
    flash("Event created successfully!", "success")
    return redirect(url_for("home"))

@app.route("/register", methods=["POST"])
def register():
    student = Student(request.form["student_id"].strip(), request.form["student_name"].strip(),
                      request.form["email"].strip(), request.form["department"].strip())
    event_id = request.form["event_id"]
    events = read_rows(EVENTS_FILE)
    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        flash("Invalid Event ID. Please choose an existing event.", "error")
        return redirect(url_for("home"))
    regs = read_rows(REG_FILE)
    if any(r["student_id"] == student.student_id and r["event_id"] == event_id for r in regs):
        flash("This student is already registered for this event.", "error")
        return redirect(url_for("home"))
    if participant_count(event_id) >= int(event["max_participants"]):
        flash("Sorry, this event is full.", "error")
        return redirect(url_for("home"))
    students = read_rows(STUDENTS_FILE)
    existing = next((s for s in students if s["student_id"] == student.student_id), None)
    if existing and (existing["name"] != student.name or existing["email"] != student.email):
        flash("Student ID already exists with different details.", "error")
        return redirect(url_for("home"))
    if not existing:
        with open(STUDENTS_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([student.student_id, student.name, student.email, student.department])
    with open(REG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([student.student_id, event_id])
    flash("Student registered successfully!", "success")
    return redirect(url_for("home"))

@app.route("/cancel", methods=["POST"])
def cancel():
    sid, eid = request.form["student_id"].strip(), request.form["event_id"].strip()
    rows = read_rows(REG_FILE)
    new_rows = [r for r in rows if not (r["student_id"] == sid and r["event_id"] == eid)]
    if len(new_rows) == len(rows):
        flash("Registration not found.", "error")
    else:
        write_rows(REG_FILE, ["student_id", "event_id"], new_rows)
        flash("Registration cancelled.", "success")
    return redirect(url_for("home"))

@app.route("/search", methods=["POST"])
def search():
    sid = request.form["student_id"].strip()
    students = read_rows(STUDENTS_FILE)
    regs = read_rows(REG_FILE)
    found = next((s for s in students if s["student_id"] == sid), None)
    if found:
        found = dict(found)
        found["event_ids"] = [r["event_id"] for r in regs if r["student_id"] == sid]
    events = read_rows(EVENTS_FILE)
    for e in events:
        e["registered"] = participant_count(e["event_id"])
        e["seats_left"] = max(0, int(e["max_participants"]) - e["registered"])
    feedback = read_rows(FEEDBACK_FILE)
    average = round(sum(int(f["rating"]) for f in feedback) / len(feedback), 2) if feedback else 0
    make_chart()
    return render_template("index.html", events=events, students=students, registrations=regs,
                           feedback_count=len(feedback), average=average, search_result=found)

@app.route("/feedback", methods=["POST"])
def feedback():
    sid, eid = request.form["student_id"].strip(), request.form["event_id"].strip()
    rating = int(request.form["rating"])
    if not any(r["student_id"] == sid and r["event_id"] == eid for r in read_rows(REG_FILE)):
        flash("Only registered students can submit feedback.", "error")
        return redirect(url_for("home"))
    if any(f["student_id"] == sid and f["event_id"] == eid for f in read_rows(FEEDBACK_FILE)):
        flash("Feedback already submitted for this event.", "error")
        return redirect(url_for("home"))
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([sid, eid, rating])
    flash("Feedback saved successfully!", "success")
    return redirect(url_for("home"))

@app.route("/analysis")
def analysis():
    feedback = read_rows(FEEDBACK_FILE)
    if feedback:
        df = pd.DataFrame(feedback)
        df["rating"] = pd.to_numeric(df["rating"])
        average = round(df["rating"].mean(), 2)
        rating_counts = df["rating"].value_counts().sort_index().to_dict()
    else:
        average, rating_counts = 0, {}
    events = read_rows(EVENTS_FILE)
    regs = read_rows(REG_FILE)
    participation = {e["name"]: sum(1 for r in regs if r["event_id"] == e["event_id"]) for e in events}
    return render_template("analysis.html", average=average, feedback_count=len(feedback),
                           rating_counts=rating_counts, participation=participation)

if __name__ == "__main__":
    app.run(debug=True)
