document.addEventListener('DOMContentLoaded', () => {
  // Initialize markdown parser and highlighter
  marked.setOptions({
    breaks: true,
    highlight: (code, language) => {
      const validLang = hljs.getLanguage(language) ? language : 'plaintext';
      return hljs.highlight(code, { language: validLang }).value;
    }
  });

  // Global current session ID
  window.currentSessionId = document.querySelector('.session-link')?.getAttribute('data-session-id') || 0;

  // Session link handling
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

  // Initial history load
  loadChatHistory(window.currentSessionId);

  // Form submission
  document.getElementById('chat-form').addEventListener('submit', handleChatSubmit);
});
// Function to load chat history
// This function fetches the chat history from the server using Fetch API 
function loadChatHistory(sessionId) {
  fetch(`/chat_history/${sessionId}`)
    .then(response => response.json())
    .then(history => {
      const chatWindow = document.getElementById('chat-window');
      chatWindow.innerHTML = "";
      history.forEach(msg => {
        appendMessage(msg.content, !msg.is_user);
      });
      chatWindow.scrollTop = chatWindow.scrollHeight;
    })
    .catch(error => console.error('Error loading chat history:', error));
}
// Function to handle chat form submission
// This function prevents the default form submission, retrieves the message input, 
// and sends the message to the server using Fetch API
// It also handles the response by streaming it back to the chat window
function handleChatSubmit(event) {
  event.preventDefault();
  const messageInput = document.getElementById('message-input');
  const userMessage = messageInput.value.trim();
  if (!userMessage) return;

  messageInput.value = "";
  appendMessage(userMessage, false);
  clearTempBotMessage();

  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) submitBtn.disabled = true;

  fetch('/send_message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      message: userMessage, 
      session_id: window.currentSessionId 
    })
  })
    .then(response => streamBotResponse(response.body))
    .catch(error => {
      console.error('Error:', error);
      if (submitBtn) submitBtn.disabled = false;
    });
}
//**
// Function to handle streaming bot response
// This function reads the response body in chunks and updates the message in real-time
// It uses the Fetch API's ReadableStream to read the response body
function streamBotResponse(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let botMessage = "";

  function read() {
    reader.read().then(({ done, value }) => {
      if (done) {
        finalizeBotMessage(botMessage);
        return;
      }
      
      botMessage += decoder.decode(value, { stream: true });
      updateTempBotMessage(botMessage);
      read();
    });
  }
  read();
}
// Function to append a message to the chat window
// This function creates a new message element and appends it to the chat window  
function appendMessage(text, isBot) {
  const chatWindow = document.getElementById('chat-window');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isBot ? 'bot' : 'user'}`;
  
  const content = isBot 
    ? DOMPurify.sanitize(marked.parse(text))
    : DOMPurify.sanitize(text);

  messageDiv.innerHTML = `
    <div class="message-content">${content}</div>
    <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
  `;

  chatWindow.appendChild(messageDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  if (isBot) {
    messageDiv.querySelectorAll('pre code').forEach(block => {
      hljs.highlightElement(block);
    });
  }
}
// Function to update the temporary bot message
// This function creates or updates a temporary message element while the bot is typing
function updateTempBotMessage(text) {
  let tempEl = document.getElementById('temp-bot-message');
  if (!tempEl) {
    tempEl = document.createElement('div');
    tempEl.id = 'temp-bot-message';
    tempEl.className = 'message bot';
    document.getElementById('chat-window').appendChild(tempEl);
  }

  const parsedContent = DOMPurify.sanitize(marked.parse(text));
  tempEl.innerHTML = `
    <div class="message-content">${parsedContent}</div>
    <div class="message-time">Typing...</div>
  `;

  tempEl.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });
  
  document.getElementById('chat-window').scrollTop = document.getElementById('chat-window').scrollHeight;
}
// Function to clear the temporary bot message
// This function removes the temporary message element from the chat window
function clearTempBotMessage() {
  const tempEl = document.getElementById('temp-bot-message');
  if (tempEl) tempEl.remove();
}
// Function to finalize the bot message
// This function clears the temporary message and appends the final bot message
function finalizeBotMessage(text) {
  clearTempBotMessage();
  appendMessage(text, true);
  document.getElementById('submit-btn').disabled = false;
}