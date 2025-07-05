from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
import pyotp
import random
import os
import sqlite3
import base64

app = Flask(__name__)
app.secret_key = "supersecretkey"

otp_store = {}

# Dummy database for fingerprint storage
fingerprint_db = {}
registered_fingerprints = {}


def get_db_connection():
    conn = sqlite3.connect('voting_system.db')
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = sqlite3.connect('voting_system.db')
    cursor = conn.cursor()
    
    # Create Candidates Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')

    # Create Votes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            aadhaar TEXT NOT NULL UNIQUE,
            mobile TEXT NOT NULL,
            candidate TEXT NOT NULL
        )
    ''')


    conn.commit()
    conn.close()
    print("Database initialized successfully!")

initialize_db()


# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voting_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define Database Models
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voter_aadhaar = db.Column(db.String(12), unique=True, nullable=False)
    selected_candidate = db.Column(db.String(100), nullable=False)

class Voter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    aadhaar_number = db.Column(db.String(12), unique=True, nullable=False)
    mobile = db.Column(db.String(10), unique=True, nullable=False)  # ✅ Make sure mobile exists
    fingerprint_data = db.Column(db.Text, nullable=True)  # ✅ Store fingerprint data here


# Store Admin Credentials
admins = {
    "admin1": "password123",
    "admin2": "securepass456",
    "admin3": "admin789"
}

candidates = {}
results = {}

# Store Candidates & Votes
candidates = {}
votes = {}

# Create database tables
with app.app_context():
    db.create_all()

# Store OTPs temporarily
otp_storage = {}

# -------------------- ROUTES --------------------

# 1️⃣ Index Page
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin_id = request.form["admin_id"]
        password = request.form["password"]
        
        if admin_id in admins and admins[admin_id] == password:
            session['admin'] = admin_id  # Store session data
            return redirect(url_for("admin_panel"))
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    
    return render_template("admin_login.html")

@app.route("/admin_panel")
def admin_panel():
    if "admin" in session:
        return render_template("admin_panel.html", admin_id=session["admin"], results=results)
    else:
        return redirect(url_for("admin_login"))

@app.route('/add_candidate', methods=['POST'])
def add_candidate():
    if "admin" in session:
        candidate_name = request.form["candidate_name"]
        conn = get_db_connection()
        conn.execute('INSERT INTO candidates (name) VALUES (?)', (candidate_name,))
        conn.commit()
        conn.close()
        
        return redirect(url_for("admin_panel"))
    return redirect(url_for("admin_login"))

@app.route('/remove_candidate', methods=['POST'])
def remove_candidate():
    if "admin" in session:
        candidate_name = request.form["remove_candidate_name"]
        conn = get_db_connection()
        conn.execute('DELETE FROM candidates WHERE name = ?', (candidate_name,))
        conn.commit()
        conn.close()
        
        return redirect(url_for("admin_panel"))
    return redirect(url_for("admin_login"))

@app.route('/get_candidates', methods=['GET'])
def get_candidates():
    conn = get_db_connection()
    candidates = [row['name'] for row in conn.execute('SELECT name FROM candidates').fetchall()]
    conn.close()
    return jsonify(candidates)

# 6️⃣ Voting Page
@app.route('/voting', methods=['GET', 'POST'])
def voting():
    conn = get_db_connection()
    candidates = [row['name'] for row in conn.execute('SELECT name FROM candidates').fetchall()]
    conn.close()
    
    if request.method == 'POST':
        name = request.form['name']
        aadhaar = request.form['aadhaar']
        mobile = request.form['mobile']
        otp = request.form['otp']
        candidate = request.form['candidate']
        fingerprint = request.form['fingerprint']  # Get fingerprint data
        scan_fingerprint = request.form['scan_fingerprint']  # Scan fingerprint

        if session.get('otp') and str(session['otp']) == otp:
            if fingerprint == scan_fingerprint:  # Verify fingerprint match
               conn = get_db_connection()
               conn.execute('INSERT INTO votes (name, aadhaar, mobile, candidate, fingerprint, scan_fingerprint) VALUES (?, ?, ?, ?, ?, ?)', 
                         (name, aadhaar, mobile, candidate, fingerprint, scan_fingerprint))
               conn.commit()
               conn.close()
               return "Vote Successfully Casted!"
            else:
                return "Fingerprint Authentication Failed!"
        else:
            return "Invalid OTP!"
    
    return render_template('voting.html', candidates=candidates)


@app.route("/webauthn/challenge", methods=["GET"])
def get_challenge():
    """Generate a challenge for WebAuthn fingerprint authentication."""
    challenge = os.urandom(32)  # Generate a random challenge
    session["challenge"] = base64.b64encode(challenge).decode("utf-8")  # Store in session
    print(f"Generated challenge: {challenge}")

    return jsonify({"challenge": list(challenge)})

    
    
@app.route("/register_fingerprint", methods=["POST"])
def register_fingerprint():
    data = request.get_json()

    if not data or "fingerprint_data" not in data or "mobile" not in data:
        return jsonify({"success": False, "message": "Fingerprint data and mobile number are required"}), 400

    mobile = data["mobile"]

    user = Voter.query.filter_by(mobile=mobile).first()  # ✅ Use Voter model, not Vote
    if user:
        try:
            user.fingerprint_data = data["fingerprint_data"]
            db.session.commit()
            return jsonify({"success": True, "message": "Fingerprint registered successfully!"})
        except Exception as e:
            print("Error saving fingerprint:", str(e))
            return jsonify({"success": False, "message": "Database error!"}), 500

    return jsonify({"success": False, "message": "User not found"}), 404




@app.route("/submit_vote", methods=["POST"])
def submit_vote():
    data = request.get_json()
    if not data or "candidate" not in data:
        return jsonify({"success": False, "message": "Candidate selection is required"}), 400

    candidate = data["candidate"]

    # ✅ Simulate saving the vote (replace with database logic)
    print(f"Vote received for: {candidate}")

    return jsonify({"success": True, "redirect": "/vote_success"})  # Redirect URL
    

@app.route('/vote_success')
def vote_success():
    return render_template('vote_success.html')


# Send OTP Route
@app.route('/send_otp', methods=['GET'])
def send_otp():
    mobile = request.args.get('mobile')
    otp = random.randint(100000, 999999)
    session['otp'] = otp

    # Twilio Configuration
    account_sid = 'AC0780ec44df26059d372322b4a7647009'  # Replace with your Twilio SID
    auth_token = '8d535484268320d42285538fc1bd8a2c'  # Replace with your Twilio Auth Token
    twilio_number = '+18064911555'  # Your Twilio Phone Number
    
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=f'Your OTP for voting is: {otp}',
        from_=twilio_number,
        to=f'+91{mobile}'  # Adjust country code as needed
    )
    return jsonify({'status': 'OTP Sent'})

@app.route('/verify_otp', methods=['GET'])
def verify_otp():
    entered_otp = request.args.get('otp')

    if 'otp' in session and str(session['otp']) == entered_otp:
        return jsonify({"verified": True, "message": "OTP Verified Successfully ✅"})
    return jsonify({"verified": False, "message": "Incorrect OTP ❌"})


@app.route("/results")
def show_results():
    if "admin" in session:
        return render_template("results.html", results=results)
    return redirect(url_for("admin_login"))

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

