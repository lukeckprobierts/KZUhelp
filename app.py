from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify, stream_with_context
from config import Config
from extensions import db  # Import db from the new file
import requests
import json
from werkzeug.security import generate_password_hash, check_password_hash
import ollama
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Import models AFTER db is initialized
from models import User, ChatSession, Message



# Helper: Login required decorator

from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Routes for Authentication

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Username and password required", "danger")
            return redirect(url_for('register'))
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "warning")
            return redirect(url_for('register'))
        # Create user and hash password
        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for('chat'))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

# Chat Interface & Session Management, setting up routes for chat sessions, login, registration, and chat history.

@app.route('/')
@login_required
def index():
    return redirect(url_for('chat'))

@app.route('/chat')
@login_required
def chat():
    # Load user sessions for sidebar
    user_sessions = ChatSession.query.filter_by(user_id=session["user_id"]).all()
    if not user_sessions:
        # Create a default session if none exists
        default_session = ChatSession(name="Default Chat", user_id=session["user_id"])
        db.session.add(default_session)
        db.session.commit()
        user_sessions = [default_session]
    return render_template("chat.html", sessions=user_sessions)


@app.route('/create_session', methods=['POST'])
@login_required
def create_session():
    name = request.form.get("session_name", "New Chat")
    new_session = ChatSession(name=name, user_id=session["user_id"])
    db.session.add(new_session)
    db.session.commit()
    return redirect(url_for('chat'))

@app.route('/rename_session/<int:session_id>', methods=['POST'])
@login_required
def rename_session(session_id):
    new_name = request.form.get("new_name")
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if chat_session and new_name:
        chat_session.name = new_name
        db.session.commit()
    return redirect(url_for('chat'))

@app.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if chat_session:
        db.session.delete(chat_session)
        db.session.commit()
    return redirect(url_for('chat'))

@app.route('/chat_history/<int:session_id>')
@login_required
def chat_history(session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first_or_404()
    messages = Message.query.filter_by(session_id=chat_session.id).order_by(Message.timestamp.asc()).all()
    history = [{"is_user": msg.is_user, "content": msg.content, "timestamp": msg.timestamp.isoformat()} for msg in messages]
    return jsonify(history)

# Chat message sending and streaming response

OLLAMA_API_URL = "http://localhost:11434/api/generate"



def stream_and_save_response(user_message, chat_session):
    complete_response = ""
    try:
        # Call the Ollama chat function with the hardcoded model.
        # have to replace this with a choose model function later.
        # For now, we are using the gemma3:27b model, best thing that runs on my current nvidia p40 gpu.
        # The stream=True parameter allows for streaming responses.
        # The generator yields each chunk of the response as it's received., yield is used instead of return because we want to stream the response.
        # The stream_with_context function keeps the request context active while streaming.
        stream = ollama.chat('gemma3:27b', [{'role': 'user', 'content': user_message}], stream=True)
        for chunk in stream:
            text_chunk = chunk['message']['content']
            complete_response += text_chunk
            yield text_chunk  # Yield each chunk as it's received.
        yield "\n"  # Optionally yield a new line.
    except Exception as e:
        error_msg = f"Error: {e}"
        yield error_msg
        complete_response = error_msg
    # Save the complete response to the DB.
    bot_msg = Message(session_id=chat_session.id, is_user=False, content=complete_response)
    db.session.add(bot_msg)
    db.session.commit()

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.get_json()
    user_message = data.get("message")
    session_id = data.get("session_id")

    # make sure the chat session exists.
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if not chat_session:
        return jsonify({"error": "Chat session not found"}), 404

    # Save the user's message.
    user_msg = Message(session_id=chat_session.id, is_user=True, content=user_message)
    db.session.add(user_msg)
    db.session.commit()

    # Wrap the generator with stream_with_context to keep the request context active.
    return Response(
        stream_with_context(stream_and_save_response(user_message, chat_session)),
        mimetype='text/plain'
    )



# Run the application

if __name__ == '__main__':
    # Create DB tables if they don't exist yet.
    with app.app_context():
        db.create_all()
    app.run(debug=True)
