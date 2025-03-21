from flask import Flask, render_template, request, Response, stream_with_context
from config import Config
from ollama import chat
import uuid

app = Flask(__name__)
app.config.from_object(Config)

# Dictionary to store conversation history for each session
conversation_histories = {}

def ChatBot_query(session_id, prompt):
    # Retrieve the conversation history for the session
    conversation_history = conversation_histories.get(session_id, [])
    
    # Add the new user prompt to the conversation history
    conversation_history.append({'role': 'user', 'content': prompt})
    
    # Call the chat API with the updated conversation history
    stream = chat(
        model='gemma3:27b',
        messages=conversation_history,
        stream=True,
    )
    
    # Process the response and update the conversation history
    for chunk in stream:
        message_content = chunk['message']['content']
        conversation_history.append({'role': 'assistant', 'content': message_content})
        conversation_histories[session_id] = conversation_history  # Save the updated conversation history
        yield f"{message_content}"

@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_input = request.form['inputText']
        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        response = Response(stream_with_context(ChatBot_query(session_id, user_input)), content_type='text/event-stream')
        response.set_cookie('session_id', session_id)
        return response
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
