from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify, stream_with_context
from config import Config
from extensions import db  # Import db from the new file
from werkzeug.security import generate_password_hash, check_password_hash
import ollama
import chromadb
from chromadb.utils import embedding_functions
from rag_utils import init_chromadb, query_context, process_uploaded_file
import os
from werkzeug.utils import secure_filename
import datetime



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
        # Retrieve the conversation history, excluding the latest user message
        messages = Message.query.filter_by(session_id=chat_session.id).order_by(Message.timestamp.asc()).all()
        conversation_history = "\n".join(
            [f"{'User' if msg.is_user else 'Bot'}: {msg.content}" for msg in messages[:-1]]  # Exclude the last message
        )

        # Retrieve context from ChromaDB with a stricter similarity threshold
        context = query_context(user_message, n_results=5, similarity_threshold=1.5)

        # Combine the context, conversation history, and user's message
        if context:
            prompt = f"role: you are the official KZU-AI, the AI tutor/assistant of the kantonsschule zürcher unterland, Your job is to help students/users in any way they needy you have an RAG built into you that will supply you with data relevant to the context, it features old tests, presentations, homework, school assignments etc. its sorted by subject and professor, use it to help students prepare for their exams or anything else. Your only responsibility is to help students, nothing else, you will do their homework, fill out their assignemtns etc. whenever they demand. language: whatever language user talks to you in, dont speak any other language or translate to english automatically, only when asked. Context from RAG:\n{context}\n\nConversation History:\n{conversation_history}\n\nUser: {user_message}"
        else:
            prompt = f"role: you are the official KZU-AI, the AI tutor/assistant of the kantonsschule zürcher unterland, Your job is to help students/users in any way they needy you have an RAG built into you that will supply you with data relevant to the context, it features old tests, presentations, homework, school assignments etc. its sorted by subject and professor, use it to help students prepare for their exams or anything else. Your only responsibility is to help students, nothing else, you will do their homework, fill out their assignemtns etc. whenever they demand. language: whatever language user talks to you in, dont speak any other language or translate to english automatically, only when asked. Conversation History:\n{conversation_history}\n\nUser: {user_message}"

        # Call the Ollama chat function with the combined prompt
        print(f"Prompt sent to model: {prompt}")  # Debug statement
        stream = ollama.chat('gemma3:27b', [{'role': 'user', 'content': prompt}], stream=True)
        for chunk in stream:
            
            text_chunk = chunk['message']['content']
            complete_response += text_chunk  # Append the chunk to the complete response
            yield text_chunk  # Yield each chunk as it's received.
        yield "\n"  # Optionally yield a new line.

        # Log the final complete response
        print(f"Final Complete Response: {complete_response}")  # Debug statement
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

    # Make sure the chat session exists
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if not chat_session:
        return jsonify({"error": "Chat session not found"}), 404

    # Check for temporary uploaded content
    uploaded_content = temp_uploads.pop(session_id, None)
    if uploaded_content:
        # Combine user message with uploaded content
        full_message = f"{user_message}\n\n📄 Attached document: {uploaded_content['filename']}\n\nContent:\n{uploaded_content['extracted_text']}"
    else:
        full_message = user_message

    # Save the user's message
    user_msg = Message(session_id=chat_session.id, is_user=True, content=full_message)
    db.session.add(user_msg)
    db.session.commit()

    # Stream the response
    return Response(
        stream_with_context(stream_and_save_response(full_message, chat_session)),
        mimetype='text/plain'
    )


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}
# Dictionary to store temporary upload content
temp_uploads = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    session_id = request.form.get('session_id')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        try:
            # Create temporary upload directory if it doesn't exist
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(temp_path)
            
            # Process the file and add to RAG system
            extracted_text, final_path = process_uploaded_file(
                temp_path, 
                destination_dir="RAG_SCANNABLE_DOCUMENTS"
            )
            
            # Store in temporary uploads
            temp_uploads[session_id] = {
                'filename': filename,
                'extracted_text': extracted_text,
                'timestamp': datetime.datetime.now()
            }
            
            # Clean up temporary file
            os.remove(temp_path)
            
            return jsonify({
                'message': 'File processed successfully',
                'extracted_text': extracted_text,
                'stored_path': final_path,
                'added_to_rag': True
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'Invalid file type'}), 400

def cleanup_temp_uploads():
    """Clean up temporary uploads older than 1 hour"""
    current_time = datetime.datetime.now()
    expired_sessions = [
        session_id for session_id, data in temp_uploads.items()
        if (current_time - data['timestamp']).total_seconds() > 3600
    ]
    for session_id in expired_sessions:
        temp_uploads.pop(session_id, None)

# Run the application

if __name__ == '__main__':
    # Create DB tables if they don't exist yet.
    with app.app_context():
        db.create_all()
    init_chromadb("RAG_scannable_documents")  # Pass only the documents directory.
    app.run(debug=True)
