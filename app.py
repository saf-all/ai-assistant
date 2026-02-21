from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
import base64
import json
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///safai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.secret_key = 'your-secret-key-here'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

class User(UserMixin, db.Model):
    id = db.Column(db.String(80), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    token_expiry = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    mode = db.Column(db.String(20), default='chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    attachments = db.Column(db.Text)
    meta_data = db.Column(db.Text)

class ResearchNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sources = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def send_verification_email(email, token):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Verify Your SafAI Account'
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        
        verify_url = f"http://localhost:5004/verify-email?token={token}"
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #667eea;">Welcome to SafAI! 🤖</h2>
                    <p>Thank you for signing up. Please verify your email address to get started.</p>
                    <a href="{verify_url}" style="display: inline-block; margin: 20px 0; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">Verify Email</a>
                    <p style="color: #666; font-size: 14px;">Or copy this link: {verify_url}</p>
                    <p style="color: #666; font-size: 12px; margin-top: 30px;">This link expires in 24 hours.</p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def call_ai(messages, mode='chat', stream=False):
    system_prompts = {
        'chat': """You are SafAI, an advanced AI assistant created by Safal Panta. You help users learn, code, and solve problems.
        
Key capabilities:
- Explain complex topics in simple terms
- Break down problems step-by-step
- Provide code examples with explanations
- Help debug and improve code
- Answer questions across all domains

Always be helpful, clear, and educational.""",
        
        'research': """You are SafAI Research Mode, an expert research assistant created by Safal Panta.

Your research process:
1. Analyze the question thoroughly
2. Break down into sub-topics
3. Provide comprehensive, well-structured answers
4. Include key facts, statistics, and insights
5. Cite sources and references when possible
6. Suggest related topics for deeper learning

Format your research with:
- Clear sections and headings
- Bullet points for key information
- Examples and case studies
- Summary and key takeaways""",
        
        'learn': """You are SafAI Learning Mode, a patient teacher created by Safal Panta.

Teaching approach:
1. Start with fundamentals
2. Use analogies and real-world examples
3. Build concepts progressively
4. Include practice exercises
5. Check understanding with questions
6. Provide additional resources

Always:
- Explain WHY, not just HOW
- Use simple language first, then technical terms
- Encourage questions and curiosity
- Adapt to the learner's pace""",
        
        'code': """You are SafAI Code Mode, an expert programming assistant created by Safal Panta.

You help with:
- Writing clean, efficient code
- Debugging and fixing errors
- Code review and optimization
- Best practices and patterns
- Architecture and design decisions

Always:
- Explain your code with comments
- Show multiple approaches when relevant
- Point out potential issues
- Suggest improvements
- Follow language-specific conventions"""
    }
    
    system_msg = {'role': 'system', 'content': system_prompts.get(mode, system_prompts['chat'])}
    messages_with_system = [system_msg] + messages
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": "arcee-ai/trinity-large-preview:free",
            "messages": messages_with_system
        },
        timeout=60
    )
    result = response.json()
    if 'error' in result:
        return f"Error: {result['error'].get('message', 'Unknown error')}"
    return result['choices'][0]['message']['content']

def deep_research(query):
    """Perform deep research on a topic"""
    research_prompt = f"""Conduct comprehensive research on: {query}

Provide:
1. Overview and Context
2. Key Concepts and Definitions
3. Important Facts and Statistics
4. Different Perspectives/Approaches
5. Practical Applications
6. Common Misconceptions
7. Learning Resources
8. Summary and Key Takeaways

Be thorough, educational, and well-structured."""
    
    messages = [{'role': 'user', 'content': research_prompt}]
    return call_ai(messages, mode='research')

@app.route('/')
@login_required
def index():
    mode = request.args.get('mode', 'chat')
    conversations = Conversation.query.filter_by(
        user_id=current_user.id,
        mode=mode
    ).order_by(Conversation.updated_at.desc()).all()
    return render_template('index.html', conversations=conversations, current_mode=mode)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            if not user.is_verified:
                flash('Please verify your email first. Check your inbox.', 'error')
                return render_template('login.html')
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('signup.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return render_template('signup.html')
        
        # Create user
        user_id = secrets.token_urlsafe(16)
        verification_token = secrets.token_urlsafe(32)
        
        # Auto-verify if SMTP not configured (development mode)
        is_verified = not SMTP_EMAIL or not SMTP_PASSWORD
        
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            verification_token=verification_token if not is_verified else None,
            token_expiry=datetime.now() + timedelta(hours=24) if not is_verified else None,
            is_verified=is_verified
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Send verification email if SMTP configured
        if not is_verified:
            if send_verification_email(email, verification_token):
                flash('Account created! Please check your email to verify.', 'success')
            else:
                flash('Account created but email failed. Contact support.', 'warning')
        else:
            flash('Account created! You can now login.', 'success')
        
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/verify-email')
def verify_email():
    token = request.args.get('token')
    
    user = User.query.filter_by(verification_token=token).first()
    
    if not user:
        flash('Invalid verification link', 'error')
        return redirect(url_for('login'))
    
    if user.token_expiry and user.token_expiry < datetime.now():
        flash('Verification link expired. Please request a new one.', 'error')
        return redirect(url_for('login'))
    
    user.is_verified = True
    user.verification_token = None
    user.token_expiry = None
    db.session.commit()
    
    flash('Email verified! You can now login.', 'success')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/conversation/<int:conv_id>')
@login_required
def conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return "Unauthorized", 403
    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.timestamp).all()
    return jsonify({
        'messages': [{
            'role': m.role,
            'content': m.content,
            'attachments': m.attachments,
            'meta_data': m.meta_data
        } for m in messages],
        'mode': conv.mode
    })

@app.route('/new-conversation', methods=['POST'])
@login_required
def new_conversation():
    data = request.json
    title = data.get('title', 'New Chat')
    mode = data.get('mode', 'chat')
    conv = Conversation(user_id=current_user.id, title=title, mode=mode)
    db.session.add(conv)
    db.session.commit()
    return jsonify({'id': conv.id})

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.json
        conv_id = data.get('conversation_id')
        user_message = data.get('message')
        attachments = data.get('attachments', [])
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        conv = Conversation.query.get_or_404(conv_id)
        if conv.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Save user message
        msg = Message(
            conversation_id=conv_id,
            role='user',
            content=user_message,
            attachments=json.dumps(attachments) if attachments else None
        )
        db.session.add(msg)
        db.session.flush()
        
        # Get conversation history
        history = Message.query.filter_by(conversation_id=conv_id).order_by(Message.timestamp).all()
        messages = [{'role': m.role, 'content': m.content} for m in history]
        
        # Get AI response
        ai_response = call_ai(messages, mode=conv.mode)
        
        # Save AI response
        ai_msg = Message(conversation_id=conv_id, role='assistant', content=ai_response)
        db.session.add(ai_msg)
        
        # Update conversation
        conv.updated_at = datetime.utcnow()
        if conv.title == 'New Chat':
            conv.title = user_message[:50]
        
        db.session.commit()
        
        return jsonify({'response': ai_response})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/deep-research', methods=['POST'])
@login_required
def research():
    data = request.json
    query = data.get('query')
    conv_id = data.get('conversation_id')
    
    # Create new conversation if not provided
    if not conv_id:
        conv = Conversation(user_id=current_user.id, title=f"Research: {query[:50]}", mode='research')
        db.session.add(conv)
        db.session.commit()
        conv_id = conv.id
    else:
        conv = Conversation.query.get(conv_id)
    
    # Save user query
    user_msg = Message(conversation_id=conv_id, role='user', content=f"🔍 Deep Research: {query}")
    db.session.add(user_msg)
    
    # Perform deep research
    research_result = deep_research(query)
    
    # Save AI response
    ai_msg = Message(conversation_id=conv_id, role='assistant', content=research_result)
    db.session.add(ai_msg)
    
    # Save as research note
    note = ResearchNote(
        user_id=current_user.id,
        title=query[:200],
        content=research_result
    )
    db.session.add(note)
    
    conv.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'result': research_result, 'note_id': note.id, 'conversation_id': conv_id})

@app.route('/research-notes')
@login_required
def research_notes():
    notes = ResearchNote.query.filter_by(user_id=current_user.id).order_by(ResearchNote.created_at.desc()).all()
    return jsonify({'notes': [{
        'id': n.id,
        'title': n.title,
        'content': n.content,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notes]})

@app.route('/upload-file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(filepath):
        filename = f"{base}_{counter}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        counter += 1
    
    file.save(filepath)
    
    file_url = f"/uploads/{filename}"
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        with open(filepath, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({'success': True, 'filename': filename, 'url': file_url, 'data': file_data})
    
    return jsonify({'success': True, 'filename': filename, 'url': file_url})

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/delete-conversation/<int:conv_id>', methods=['POST'])
@login_required
def delete_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    Message.query.filter_by(conversation_id=conv_id).delete()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5004, debug=True)
