# Chatbot App

This is a fully functional chatbot website built with Flask that mimics ChatGPT’s functionality and is built for easy implementation with RAG. It integrates with a locally running Ollama instance (model: `gemma3:27b`), supports streaming responses, secure user authentication, and chat session management stored in a relational database.

## Features

- **Backend & Model Integration:**  
  Uses Flask and integrates with a local Ollama API endpoint at `http://localhost:11434/api/generate`.

- **Streaming Responses:**  
  Responses are streamed in real-time using Flask’s streaming support and the Fetch API on the frontend.

- **User Authentication:**  
  Secure login, registration, and logout functionalities with password hashing via Werkzeug.

- **Chat Session Management:**  
  Each user can create, rename, delete, and view chat sessions and message history stored in SQLite via SQLAlchemy.

- **Responsive Frontend:**  
  HTML/CSS interface built with Bootstrap providing a ChatGPT-like chat experience.

- **hardware requirements**
  With gemma3:27b as the LLM I recommend at least 20GB of vram. Adjust for smaller VRAM by using smaller models or accepting lower speeds
## Setup Instructions
-run the app.py File, this will host the entire thing on a localhost. This is only for test purposes right now as I plan to host this on my local device to make it a Web-App. Also usable for local homelabs/servers. Cloud hosting not recommended since GPU servers are wildly expensive compared to using API calls.