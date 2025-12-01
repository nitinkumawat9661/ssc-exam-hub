import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import requests
import json
import random

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'ssc_super_secret_key_2025_nitin_final'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ssc_hub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROFILE_PICS'] = 'static/profile_pics'

# Render HTTPS Cookies
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

API_KEY = "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"

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

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad_reward = db.Column(db.Integer, default=20)
    exam_date = db.Column(db.String(20), default="2025-12-31")
    notice_text = db.Column(db.String(200), default="Welcome to SSC Hub!")

# --- HELPERS ---
def get_greeting(user):
    hour = datetime.now().hour
    salutation = user.name.split()[0] if user.name else "Student"
    if user.gender == "Male": salutation = "Sir"
    elif user.gender == "Female": salutation = "Ma'am"
    today = datetime.now().strftime("%m-%d")
    if user.dob and user.dob.endswith(today): return f"Happy Birthday, {salutation}! 🎂"
    if hour < 12: return f"Good Morning, {salutation}! ☀️"
    elif hour < 18: return f"Good Afternoon, {salutation}! 🌤️"
    else: return f"Good Evening, {salutation}! 🌙"

def check_streak(user):
    today = datetime.now().strftime("%Y-%m-%d")
    if user.last_login != today:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if user.last_login == yesterday: user.streak += 1
        elif user.last_login != today: user.streak = 1
        user.last_login = today
        db.session.commit()

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
            if data.get('phone') == "+917665853321": new_user.is_admin = True
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
    
    check_streak(user)
    settings = AppSettings.query.first() or AppSettings()
    if not settings.id: db.session.add(settings); db.session.commit()

    exam_dt = datetime.strptime(settings.exam_date, "%Y-%m-%d")
    days_left = (exam_dt - datetime.now()).days
    img_url = url_for('static', filename='profile_pics/' + user.image_file) if user.image_file != 'default.png' else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
    
    return render_template('dashboard.html', user=user, greeting=get_greeting(user), days_left=days_left, settings=settings, profile_pic=img_url, daily_fact="Keep Learning!")

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.dob = request.form.get('dob')
        user.gender = request.form.get('gender')
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(user.id + "_" + file.filename)
                file.save(os.path.join(app.config['PROFILE_PICS'], filename))
                user.image_file = filename
        db.session.commit()
        return redirect(url_for('profile'))
    img_url = url_for('static', filename='profile_pics/' + user.image_file) if user.image_file != 'default.png' else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
    return render_template('profile.html', user=user, badges=json.loads(user.badges), profile_pic=img_url)

@app.route('/library')
def library():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    return render_template('library.html', user=user, papers=Paper.query.all(), owned_ids=json.loads(user.papers_owned))

@app.route('/buy_paper/<int:paper_id>')
def buy_paper(paper_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    paper = Paper.query.get(paper_id)
    owned = json.loads(user.papers_owned)
    if paper_id not in owned and user.coins >= paper.price:
        user.coins -= paper.price
        owned.append(paper_id)
        user.papers_owned = json.dumps(owned)
        db.session.commit()
    return redirect(url_for('library'))

@app.route('/flashcards')
def flashcards():
    if 'user_id' not in session: return redirect(url_for('index'))
    return render_template('flashcards.html', cards=Flashcard.query.all())

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    question = request.form.get('question')
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://sscexamhub.onrender.com"}
    data = {"model": "meta-llama/llama-3-8b-instruct:free", "messages": [{"role": "user", "content": question}]}
    try: return jsonify({'answer': requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()['choices'][0]['message']['content']})
    except: return jsonify({'answer': "AI Error."})

@app.route('/watch_ad', methods=['POST'])
def watch_ad():
    if 'user_id' not in session: return jsonify({})
    user = User.query.get(session['user_id'])
    user.coins += 20
    db.session.commit()
    return jsonify({'new_balance': user.coins})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if not user.is_admin: return "Access Denied"
    if request.method == 'POST':
        if 'paper_title' in request.form:
            file = request.files['file']
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.session.add(Paper(title=request.form['paper_title'], category="SSC", price=int(request.form['price']), filename=filename))
            db.session.commit()
        elif 'fc_q' in request.form:
            db.session.add(Flashcard(question=request.form['fc_q'], answer=request.form['fc_a'], category="General"))
            db.session.commit()
    return render_template('admin.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# --- SAFE INIT (No Reset) ---
with app.app_context():
    db.create_all() # Only creates if not exists
    if not os.path.exists('uploads'): os.makedirs('uploads')
    if not os.path.exists('static/profile_pics'): os.makedirs('static/profile_pics')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
