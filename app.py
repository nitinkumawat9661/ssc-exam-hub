import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ssc_hub_secure_key_999'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ssc_hub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

API_KEY = "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"

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    coins = db.Column(db.Integer, default=50)
    is_admin = db.Column(db.Boolean, default=False)

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    category = db.Column(db.String(50))
    price = db.Column(db.Integer)
    filename = db.Column(db.String(200))

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad_reward = db.Column(db.Integer, default=10)

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/firebase_login', methods=['POST'])
def firebase_login():
    data = request.json
    uid = data.get('uid')
    email = data.get('email', '')
    phone = data.get('phone', '')
    name = data.get('name', 'Student')

    user = User.query.get(uid)
    if not user:
        new_user = User(id=uid, name=name, email=email, phone=phone, coins=50)
        if phone == "+917665853321":
            new_user.is_admin = True
        db.session.add(new_user)
        db.session.commit()
    
    session['user_id'] = uid
    return jsonify({'status': 'success'})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    papers = Paper.query.all()
    settings = AppSettings.query.first()
    if not settings:
        settings = AppSettings(ad_reward=10)
        db.session.add(settings)
        db.session.commit()

    return render_template('dashboard.html', user=user, papers=papers, ad_reward=settings.ad_reward)

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    if 'user_id' not in session:
        return jsonify({'answer': 'Login First'})
    
    question = request.form.get('question')
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ssc-exam-hub.onrender.com",
        "X-Title": "SSC Exam Hub"
    }
    data = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [
            {"role": "system", "content": "You are an SSC teacher. Explain in Hindi."}, 
            {"role": "user", "content": question}
        ]
    }
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers)
        ans = resp.json()['choices'][0]['message']['content']
        return jsonify({'answer': ans})
    except Exception as e:
        return jsonify({'answer': f"Error: {str(e)}"})

@app.route('/watch_ad', methods=['POST'])
def watch_ad():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    user = User.query.get(session['user_id'])
    settings = AppSettings.query.first()
    user.coins += settings.ad_reward
    db.session.commit()
    return jsonify({'success': True, 'new_balance': user.coins, 'msg': f'+{settings.ad_reward} Coins!'})

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return "Access Denied"

    settings = AppSettings.query.first()
    if request.method == 'POST':
        if 'ad_rate' in request.form:
            settings.ad_reward = int(request.form.get('ad_rate'))
            db.session.commit()
        elif 'paper_title' in request.form:
            file = request.files['file']
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_paper = Paper(
                    title=request.form.get('paper_title'),
                    category="SSC",
                    price=int(request.form.get('price')),
                    filename=filename
                )
                db.session.add(new_paper)
                db.session.commit()
    
    return render_template('admin.html', settings=settings)

# --- INITIALIZE DATABASE ---
with app.app_context():
    db.create_all()
    # Ensure uploads folder exists
    if not os.path.exists('uploads'):
        os.makedirs('uploads')

# --- RUN APP ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
