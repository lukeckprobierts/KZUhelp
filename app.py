from flask import Flask, render_template, request, Response, stream_with_context
from config import Config
from ollama import chat

app = Flask(__name__)
app.config.from_object(Config)

def ChatBot_query(prompt):
    stream = chat(
        model='gemma3:27b',
        messages=[{'role': 'user', 'content': prompt}],
        stream=True,
    )
    for chunk in stream:
        print(chunk['message']['content'], end='', flush=True)
        yield f"{chunk['message']['content']}"

@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_input = request.form['inputText']
        return Response(stream_with_context(ChatBot_query(user_input)), content_type='text/event-stream')
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
