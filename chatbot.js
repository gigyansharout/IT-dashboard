document.addEventListener('DOMContentLoaded', () => {
    // 1. Create Launcher Floating Button
    const launcher = document.createElement('div');
    launcher.className = 'chatbot-launcher';
    launcher.id = 'chatbotLauncher';
    launcher.innerHTML = '<i class="fa-solid fa-comment-dots"></i>';
    document.body.appendChild(launcher);

    // 2. Create Chat Box Container Card
    const card = document.createElement('div');
    card.className = 'chatbot-card';
    card.id = 'chatbotCard';
    card.innerHTML = `
        <div class="chatbot-header">
            <div class="chatbot-header-info">
                <div class="chatbot-avatar">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="chatbot-header-text">
                    <h4>Nalco Assistant</h4>
                    <span>Help & Support</span>
                </div>
            </div>
            <button class="chatbot-close-btn" id="chatbotCloseBtn" title="Minimize chat">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>
        <div class="chatbot-body" id="chatbotBody">
            <div class="chat-msg support">
                Hello! Welcome to NALCO IT Portal Support. How can I help you today?
            </div>
            <div class="chatbot-chips">
                <button class="chat-chip" data-question="How to register?">How to register?</button>
                <button class="chat-chip" data-question="I forgot my password.">Forgot password?</button>
                <button class="chat-chip" data-question="Manager capabilities?">Manager role info?</button>
                <button class="chat-chip" data-question="Contact support info">Contact Support</button>
            </div>
        </div>
        <div class="chatbot-input-area">
            <input type="text" class="chatbot-input-field" id="chatbotInput" placeholder="Type a message..." autocomplete="off">
            <button class="chatbot-send-btn" id="chatbotSendBtn" title="Send message">
                <i class="fa-solid fa-paper-plane"></i>
            </button>
        </div>
    `;
    document.body.appendChild(card);

    // Elements lookup
    const chatbotBody = document.getElementById('chatbotBody');
    const chatbotInput = document.getElementById('chatbotInput');
    const chatbotSendBtn = document.getElementById('chatbotSendBtn');
    const chatbotCloseBtn = document.getElementById('chatbotCloseBtn');

    // Toggles
    const toggleChat = () => {
        card.classList.toggle('open');
        launcher.classList.toggle('active');
        if (card.classList.contains('open')) {
            chatbotInput.focus();
            scrollToBottom();
        }
    };

    launcher.addEventListener('click', toggleChat);
    chatbotCloseBtn.addEventListener('click', toggleChat);

    // Scroll helper
    const scrollToBottom = () => {
        chatbotBody.scrollTop = chatbotBody.scrollHeight;
    };

    // Render message helpers
    const appendUserMessage = (text) => {
        const msg = document.createElement('div');
        msg.className = 'chat-msg user';
        msg.innerText = text;
        chatbotBody.appendChild(msg);
        scrollToBottom();
    };

    const appendSupportMessage = (htmlText) => {
        const msg = document.createElement('div');
        msg.className = 'chat-msg support';
        msg.innerHTML = htmlText;
        chatbotBody.appendChild(msg);
        scrollToBottom();
    };

    // Render typing loader
    let loaderElement = null;
    const showTypingIndicator = () => {
        if (loaderElement) return;
        loaderElement = document.createElement('div');
        loaderElement.className = 'chat-msg support typing-loader';
        loaderElement.innerHTML = `
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        `;
        chatbotBody.appendChild(loaderElement);
        scrollToBottom();
    };

    const hideTypingIndicator = () => {
        if (loaderElement) {
            loaderElement.remove();
            loaderElement = null;
        }
    };

    // Send logic
    const handleSendMessage = async (text) => {
        const query = text.trim();
        if (!query) return;

        appendUserMessage(query);
        chatbotInput.value = '';
        showTypingIndicator();

        try {
            const res = await fetch('http://127.0.0.1:5000/api/support/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: query })
            });
            const data = await res.json();
            hideTypingIndicator();
            if (res.ok) {
                appendSupportMessage(data.reply);
            } else {
                appendSupportMessage("Oops, I encountered an issue fetching details. Please check back shortly.");
            }
        } catch (err) {
            hideTypingIndicator();
            appendSupportMessage("Connection error. Ensure the backend Flask server is running.");
        }
    };

    // Bind event listeners
    chatbotSendBtn.addEventListener('click', () => {
        handleSendMessage(chatbotInput.value);
    });

    chatbotInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            handleSendMessage(chatbotInput.value);
        }
    });

    // Handle suggestion chips
    chatbotBody.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('chat-chip')) {
            const question = e.target.getAttribute('data-question');
            handleSendMessage(question);
            // Hide the chips container after first selection to clean up UI
            const chips = chatbotBody.querySelector('.chatbot-chips');
            if (chips) {
                chips.style.opacity = '0.5';
                chips.style.pointerEvents = 'none';
            }
        }
    });
});
