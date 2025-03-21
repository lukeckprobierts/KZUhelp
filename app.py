from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from config import Config
from ollama import chat
import uuid

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html')

def ChatBot_query(user_id, prompt):
    # Retrieve the conversation history for the user
    conversation_history = Conversation.query.filter_by(user_id=user_id).all()
    
    # Add the new user prompt to the conversation history
    new_user_message = Conversation(user_id=user_id, role='user', content=prompt)
    db.session.add(new_user_message)
    db.session.commit()
    
    # Prepare the conversation history for the chat API
    messages = [{'role': conv.role, 'content': conv.content} for conv in conversation_history]
    messages.append({'role': 'user', 'content': prompt})
    
    # Call the chat API with the updated conversation history
    stream = chat(
        model='gemma3:27b',
        messages=messages,
        stream=True,
    )
    
    # Process the response and update the conversation history
    for chunk in stream:
        message_content = chunk['message']['content']
        new_assistant_message = Conversation(user_id=user_id, role='assistant', content=message_content)
        db.session.add(new_assistant_message)
        db.session.commit()
        yield f"{message_content}"

@app.route("/", methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        user_input = request.form['inputText']
        return Response(stream_with_context(ChatBot_query(current_user.id, user_input)), content_type='text/event-stream')
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
