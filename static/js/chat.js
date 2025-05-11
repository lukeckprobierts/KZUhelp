document.addEventListener('DOMContentLoaded', () => {
  // Global current session ID (default to first session from template)
  window.currentSessionId = document.querySelector('.session-link')?.getAttribute('data-session-id') || 0;
  //setting up the fundamental elements of the chatbot
  // Attach click listeners to session links to load history on selection.
  const sessionLinks = document.querySelectorAll('.session-link');
  sessionLinks.forEach(link => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      sessionLinks.forEach(s => s.classList.remove('active'));
      link.classList.add('active');
      const sessionId = link.getAttribute('data-session-id');
      window.currentSessionId = sessionId;
      loadChatHistory(sessionId);
    });
  });

  // Load history for the initial session.
  loadChatHistory(window.currentSessionId);

  // Attach form submit listener.
  document.getElementById('chat-form').addEventListener('submit', handleChatSubmit);
});
// loads the chat history for a given session ID from the server using fetch API.
// sends a GET request to the server and expects a JSON response containing the users chat history.
function loadChatHistory(sessionId) {
  fetch(`/chat_history/${sessionId}`)
    .then(response => response.json())
    .then(history => {
      const chatWindow = document.getElementById('chat-window');
      chatWindow.innerHTML = ""; // Clear existing messages.
      history.forEach(msg => {
        appendChatMessage(msg.is_user ? 'You' : 'Bot', msg.content);
      });
      chatWindow.scrollTop = chatWindow.scrollHeight;
    })
    .catch(error => console.error('Error loading chat history:', error));
}
// handles the form submission when the user sends a message.
// prevents the default form submission behavior, retrieves the message from the input field,
// appends it to the chat window, and sends the message to the server using fetch API.
// also handles the response from the server, which is expected to be a stream of data in chunks from the flask file.
function handleChatSubmit(event) {
  event.preventDefault();
  const messageInput = document.getElementById('message-input');
  const userMessage = messageInput.value;
  messageInput.value = "";
  appendChatMessage('You', userMessage);
  clearTempBotMessage();

  // Disable the submit button while waiting for the response.
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) submitBtn.disabled = true;
  // Send the message to the server.
  // The server should handle the session ID and return the bot's response.
  fetch('/send_message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: userMessage, session_id: window.currentSessionId })
  })
    .then(response => streamBotResponse(response.body))
    .catch(error => {
      console.error('Error sending message:', error);
      // In case of error, re-enable the button.
      if (submitBtn) submitBtn.disabled = false;
    });
}
// streams the bot's response in chunks.
// reads the response body as a stream and updates the chat window in real-time.
// uses the ReadableStream API to read the response in chunks and decode it using TextDecoder.
function streamBotResponse(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let botMessage = "";

  function readChunk() {
    reader.read().then(({ done, value }) => {
      if (done) {
        finalizeBotMessage(botMessage);
        return;
      }
      const chunk = decoder.decode(value);
      botMessage += chunk;
      updateTempBotMessage(botMessage);
      readChunk();
    });
  }
  readChunk();
}
//simple function to append a chat message to the chat window.
// It creates a new div element for the message, sets its inner HTML to include the sender and message text,
function appendChatMessage(sender, text) {
  const chatWindow = document.getElementById('chat-window');
  const msgDiv = document.createElement('div');
  msgDiv.innerHTML = `<strong>${sender}:</strong> ${text}`;
  chatWindow.appendChild(msgDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}
// updates the temporary bot message in the chat window while the bot is typing.
// makes it possible to show the bot's response in real-time as it is being generated.
// It creates a temporary message element and updates its content with the bot's response as it arrives.
function updateTempBotMessage(text) {
  let tempEl = document.getElementById('temp-bot-message');
  if (!tempEl) {
    tempEl = document.createElement('div');
    tempEl.id = 'temp-bot-message';
    document.getElementById('chat-window').appendChild(tempEl);
  }
  tempEl.innerHTML = `<strong>Bot:</strong> ${text}`;
  document.getElementById('chat-window').scrollTop = document.getElementById('chat-window').scrollHeight;
}
//  clears the temporary bot message from the chat window once the bot's response is complete.
//  removes the temporary message element from the chat window.
function clearTempBotMessage() {
  const tempEl = document.getElementById('temp-bot-message');
  if (tempEl) tempEl.remove();
}
// finalizes the bot's message once the response is complete.
// clears the temporary message and appends the final bot message to the chat window.
function finalizeBotMessage(text) {
  clearTempBotMessage();
  appendChatMessage('Bot', text);
  // Re-enable the submit button once the response is complete.
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) submitBtn.disabled = false;
}
