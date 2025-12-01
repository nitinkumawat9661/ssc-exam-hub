import os
import logging
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
import json
import random
import requests

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CONFIG ---
app.config['SECRET_KEY'] = 'ssc_hub_testing_key'

# 🔥 TEMPORARY TESTING DATABASE (IN-MEMORY) 🔥
# This will run the site without needing Postgres to check for other errors.
# Note: Data will be lost on every refresh, this is for testing only.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['PROFILE_PICS'] = 'static/profile_pics'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# 🔥 CREDENTIALS 🔥
ADMIN_EMAIL_DEFAULT = "nitinkumawat985@gmail.com"
EMAIL_PASSWORD = "cuzr fhda ulkq swpc"
AI_API_KEY = "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"
IST = pytz.timezone('Asia/Kolkata')

db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=True)
    coins = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    streak = db.Column(db.Integer, default=0)
    last_login = db.Column(db.String(20), nullable=True)
    badges = db.Column(db.String(500), default="[]")
    papers_owned = db.Column(db.String(1000), default="[]")
    dob = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    image_file = db.Column(db.String(100), default='default.png')

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_text = db.Column(db.String(200), default="Welcome to SSC Hub!")
    upi_id = db.Column(db.String(50), default="7665853321@paytm")
    upi_name = db.Column(db.String(50), default="Nitin Kumawat")
    admin_email = db.Column(db.String(100), default="nitinkumawat985@gmail.com")
    ads_enabled = db.Column(db.Boolean, default=True)
    ad_reward = db.Column(db.Integer, default=20)
    today_date_str = db.Column(db.String(20), nullable=True)
    today_dose_content = db.Column(db.Text, nullable=True)

class PaymentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100))
    user_name = db.Column(db.String(100))
    amount = db.Column(db.Integer)
    utr = db.Column(db.String(50))
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.String(30))

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    category = db.Column(db.String(50))
    price = db.Column(db.Integer)
    filename = db.Column(db.String(200))

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200))
    answer = db.Column(db.String(200))
    category = db.Column(db.String(50))

# --- HELPER ---
def get_smart_daily_dose():
    return "<b>💡 Test Dose:</b> Site is in Test Mode."

# --- ROUTES ---
@app.route('/')
def index():
    try:
        if 'user_id' in session: return redirect(url_for('dashboard'))
        return render_template('login.html')
    except Exception as e:
        return f"<h3>Index Error: {str(e)}</h3>"

@app.route('/firebase_login', methods=['POST'])
def firebase_login():
    try:
        data = request.json
        uid = data.get('uid')
        user = User.query.get(uid)
        if not user:
            new_user = User(id=uid, name=data.get('name', 'Student'), email=data.get('email'), phone=data.get('phone'))
            if data.get('email') == "nitinkumawat985@gmail.com": new_user.is_admin = True
            db.session.add(new_user)
            db.session.commit()
        session.permanent = True
        session['user_id'] = uid
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Login Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/dashboard')
def dashboard():
    try:
        if 'user_id' not in session: return redirect(url_for('index'))
        user = User.query.get(session['user_id'])
        if not user: session.pop('user_id', None); return redirect(url_for('index'))

        settings = AppSettings.query.first()
        if not settings: settings = AppSettings(); db.session.add(settings); db.session.commit()

        img_url = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        return render_template('dashboard.html', user=user, settings=settings, profile_pic=img_url, daily_fact=get_smart_daily_dose())
    except Exception as e:
        return f"<h3>Dashboard Error: {str(e)}</h3>"

# ... (other routes can be simplified or commented out for this test) ...
@app.route('/watch_ad', methods=['POST'])
def watch_ad(): return jsonify({'msg': 'Test Mode'})
@app.route('/submit_payment', methods=['POST'])
def submit_payment(): return redirect(url_for('dashboard'))
@app.route('/ask_ai', methods=['POST'])
def ask_ai(): return jsonify({'answer': 'AI is in Test Mode.'})
@app.route('/admin')
def admin(): return "Admin Panel is in Test Mode."
@app.route('/logout')
def logout(): session.pop('user_id', None); return redirect(url_for('index'))

# ERROR HANDLER
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server Error: {error}")
    return f"<h1>500 Error:</h1><p>{str(error)}</p>", 500

# DATABASE CREATION
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Database tables created in memory.")
    except Exception as e:
        logger.error(f"⚠️ DB Creation Error: {e}")

if __name__ == '__main__':
    app.run()
