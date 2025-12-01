import os
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

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'ssc_hub_vercel_final_v300'

# 🔥 CRITICAL DATABASE FIX FOR VERCEL 🔥
# Vercel gives 'postgres://', but SQLAlchemy requires 'postgresql://'
raw_db_url = os.environ.get('POSTGRES_URL') 
if raw_db_url:
    if raw_db_url.startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url.replace("postgres://", "postgresql://", 1)
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
else:
    # Local Fallback
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ssc_hub.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp' 
app.config['PROFILE_PICS'] = 'static/profile_pics' 

# Security Headers
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
    phone = db.Column(db.String(20))
    coins = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    streak = db.Column(db.Integer, default=0)
    last_login = db.Column(db.String(20))
    badges = db.Column(db.String(500), default="[]")
    papers_owned = db.Column(db.String(1000), default="[]")
    dob = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    image_file = db.Column(db.String(100), default='default.png')

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_text = db.Column(db.String(200), default="Welcome to SSC Hub!")
    upi_id = db.Column(db.String(50), default="7665853321@paytm")
    upi_name = db.Column(db.String(50), default="Nitin Kumawat")
    admin_email = db.Column(db.String(100), default="nitinkumawat985@gmail.com")
    ads_enabled = db.Column(db.Boolean, default=True)
    ad_reward = db.Column(db.Integer, default=20)
    today_date_str = db.Column(db.String(20))
    today_dose_content = db.Column(db.Text)

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
    try:
        settings = AppSettings.query.first()
        if not settings: settings = AppSettings(); db.session.add(settings); db.session.commit()
        
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        if settings.today_date_str == today_str and settings.today_dose_content:
            return settings.today_dose_content

        prompt = f"Generate a unique 'Daily Dose' for SSC Aspirants for {today_str}. 3 points: English Vocab, Math Trick, GK Fact. Use HTML <b> tags."
        headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://sscexamhub.onrender.com"}
        data = {"model": "meta-llama/llama-3-8b-instruct:free", "messages": [{"role": "user", "content": prompt}]}
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers)
        new_content = resp.json()['choices'][0]['message']['content']
        
        settings.today_date_str = today_str
        settings.today_dose_content = new_content
        db.session.commit()
        return new_content
    except:
        return "<b>Tip:</b> Keep revising."

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/firebase_login', methods=['POST'])
def firebase_login():
    try:
        data = request.json
        uid = data.get('uid')
        user = User.query.get(uid)
        if not user:
            new_user = User(id=uid, name=data.get('name', 'Student'), email=data.get('email'), phone=data.get('phone'), coins=100)
            if data.get('email') == "nitinkumawat985@gmail.com": 
                new_user.is_admin = True
            db.session.add(new_user)
            db.session.commit()
        session.permanent = True
        session['user_id'] = uid
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if not user: session.pop('user_id', None); return redirect(url_for('index'))
    
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if user.last_login != today:
        yesterday = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
        if user.last_login == yesterday: user.streak += 1
        elif user.last_login != today: user.streak = 1
        user.last_login = today
        db.session.commit()

    settings = AppSettings.query.first()
    if not settings: settings = AppSettings(); db.session.add(settings); db.session.commit()
    
    img_url = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

    return render_template('dashboard.html', user=user, settings=settings, profile_pic=img_url, daily_fact=get_smart_daily_dose())

@app.route('/watch_ad', methods=['POST'])
def watch_ad():
    if 'user_id' not in session: return jsonify({})
    user = User.query.get(session['user_id'])
    settings = AppSettings.query.first()
    if settings.ads_enabled:
        user.coins += settings.ad_reward
        db.session.commit()
        return jsonify({'msg': f'Earned {settings.ad_reward} Coins!'})
    return jsonify({'msg': 'Ads disabled.'})

@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'user_id' not in session: return redirect(url_for('dashboard'))
    user = User.query.get(session['user_id'])
    settings = AppSettings.query.first()
    amount = request.form.get('amount')
    utr = request.form.get('utr')
    
    if PaymentRequest.query.filter_by(utr=utr).first(): return redirect(url_for('dashboard'))

    req = PaymentRequest(user_id=user.id, user_name=user.name, amount=amount, utr=utr, created_at=datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
    db.session.add(req)
    db.session.commit()
    
    try:
        target = settings.admin_email if settings.admin_email else ADMIN_EMAIL_DEFAULT
        msg = MIMEText(f"User: {user.name}
Amount: Rs. {amount}
UTR: {utr}")
        msg['Subject'] = f"💰 Payment: Rs. {amount}"
        msg['From'] = ADMIN_EMAIL_DEFAULT
        msg['To'] = target
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(ADMIN_EMAIL_DEFAULT, EMAIL_PASSWORD)
        server.sendmail(ADMIN_EMAIL_DEFAULT, target, msg.as_string())
        server.quit()
    except: pass
    return redirect(url_for('dashboard'))

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    question = request.form.get('question')
    prompt = "You are 'SSC Guru'. Concise. Math: Tricks. GK: Mnemonics."
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://sscexamhub.onrender.com"}
    data = {"model": "meta-llama/llama-3-8b-instruct:free", "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": question}]}
    try: return jsonify({'answer': requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()['choices'][0]['message']['content']})
    except: return jsonify({'answer': "Try again."})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if not user.is_admin: return "Access Denied"
    settings = AppSettings.query.first()

    if request.method == 'POST':
        if 'update_settings' in request.form:
            settings.upi_id = request.form.get('upi_id')
            settings.upi_name = request.form.get('upi_name')
            settings.admin_email = request.form.get('admin_email')
            settings.notice_text = request.form.get('notice_text')
            settings.ads_enabled = 'ads_enabled' in request.form
            settings.ad_reward = int(request.form.get('ad_reward'))
            db.session.commit()
        elif 'paper_title' in request.form:
            db.session.add(Paper(title=request.form['paper_title'], category="SSC", price=int(request.form['price']), filename="demo.pdf"))
            db.session.commit()
        elif 'fc_q' in request.form:
            db.session.add(Flashcard(question=request.form['fc_q'], answer=request.form['fc_a'], category="General"))
            db.session.commit()
    
    pending = PaymentRequest.query.filter_by(status='pending').all()
    return render_template('admin.html', payments=pending, settings=settings)

@app.route('/approve_payment/<int:req_id>')
def approve_payment(req_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if not user.is_admin: return "Access Denied"
    req = PaymentRequest.query.get(req_id)
    if req.status == 'pending':
        req.status = "approved"
        buyer = User.query.get(req.user_id)
        buyer.coins += int(req.amount) * 10 
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/reject_payment/<int:req_id>')
def reject_payment(req_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if not user.is_admin: return "Access Denied"
    req = PaymentRequest.query.get(req_id)
    req.status = "rejected"
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# 🔥 ERROR PROOF DB CREATION 🔥
with app.app_context():
    try:
        # This will create tables only if they don't exist
        db.create_all()
        print("✅ Database Tables Checked/Created!")
    except Exception as e:
        print(f"⚠️ Database Warning: {e}")

if __name__ == '__main__':
    app.run()
