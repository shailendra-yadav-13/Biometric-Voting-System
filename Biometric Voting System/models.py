from flask_sqlalchemy import SQLAlchemy  
#from models import db, Vote, Candidate

db = SQLAlchemy() 



class User(db.Model):  
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(100), nullable=False)  
    aadhaar_number = db.Column(db.String(12), unique=True, nullable=False)  
    mobile_number = db.Column(db.String(10), unique=True, nullable=False)  
    votes = db.relationship('Vote', backref='user', lazy=True)  
    
class Candidate(db.Model):  
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(100), nullable=False)  
    votes = db.relationship('Vote', backref='candidate', lazy=True)  
    votes = db.Column(db.Integer, default=0)  # Vote count only

class Vote(db.Model):  
    id = db.Column(db.Integer, primary_key=True)  
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)  
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # If tracking users
    voter_name = db.Column(db.String(100), nullable=False)
    aadhaar = db.Column(db.String(12), nullable=False)
    candidate_name = db.Column(db.String(100), nullable=False)  
    mobile = db.Column(db.String(10), nullable=False)
