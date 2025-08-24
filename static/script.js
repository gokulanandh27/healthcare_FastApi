// Global variables
let authToken = null;
let currentUser = null;

// Initialize app when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is already logged in
    const savedToken = localStorage.getItem('authToken');
    const savedUser = localStorage.getItem('currentUser');
    
    if (savedToken && savedUser) {
        authToken = savedToken;
        currentUser = JSON.parse(savedUser);
        showMainApp();
        loadChatHistory();
        loadDocuments();
    }
    
    // Add enter key support for chat input
    document.getElementById('chat-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});

// Authentication functions
function switchTab(tab) {
    // Remove active class from all tabs and forms
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
    
    // Add active class to selected tab and form
    document.getElementById(tab + '-tab').classList.add('active');
    document.getElementById(tab + '-form').classList.add('active');
    
    // Clear any messages
    hideMessage();
}

async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    if (!username || !password) {
        showMessage('Please enter both username and password', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch('/auth/login', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            authToken = result.access_token;
            currentUser = result.user_info;
            
            // Save to localStorage
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            
            showMainApp();
            loadChatHistory();
            loadDocuments();
        } else {
            showMessage(result.detail || 'Login failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
    } finally {
        showLoading(false);
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const fullName = document.getElementById('register-fullname').value;
    const password = document.getElementById('register-password').value;
    
    if (!username || !email || !fullName || !password) {
        showMessage('Please fill in all fields', 'error');
        return;
    }
    
    if (password.length < 6) {
        showMessage('Password must be at least 6 characters', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                email: email,
                full_name: fullName,
                password: password
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showMessage('Registration successful! Please sign in.', 'success');
            switchTab('login');
            // Clear form
            document.getElementById('register-form').reset();
        } else {
            showMessage(result.detail || 'Registration failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
    } finally {
        showLoading(false);
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    
    // Show auth section, hide main section
    document.getElementById('auth-section').style.display = 'flex';
    document.getElementById('main-section').style.display = 'none';
    
    // Clear chat messages
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('document-list').innerHTML = '';
    
    // Reset forms
    document.querySelectorAll('form').forEach(form => form.reset());
}

function showMainApp() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('main-section').style.display = 'block';
    
    if (currentUser) {
        document.getElementById('user-name').textContent = currentUser.full_name;
    }
}

// File upload functions
async function handleFileUpload(event) {
    const files = Array.from(event.target.files);
    
    if (files.length === 0) return;
    
    const formData = new FormData();
    files.forEach(file => {
        if (file.type === 'application/pdf') {
            formData.append('files', file);
        }
    });
    
    if (!formData.has('files')) {
        showMessage('Please select PDF files only', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/documents/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addMessage('system', `✅ Successfully processed ${result.documents.length} documents!`);
            loadDocuments();
        } else {
            addMessage('system', `❌ Error: ${result.detail}`);
        }
    } catch (error) {
        addMessage('system', '❌ Error uploading documents. Please try again.');
    } finally {
        showLoading(false);
        event.target.value = ''; // Clear file input
    }
}

async function loadDocuments() {
    try {
        const response = await fetch('/documents/list', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        const docList = document.getElementById('document-list');
        
        if (result.documents && result.documents.length > 0) {
            docList.innerHTML = result.documents.map(doc => `
                <div class="document-item">
                    <strong>${doc.filename}</strong><br>
                    <small>Processed: ${new Date(doc.processed_at).toLocaleDateString()}</small><br>
                    <small>${doc.chunk_count} chunks</small>
                </div>
            `).join('');
        } else {
            docList.innerHTML = '<div class="document-item">No documents uploaded yet</div>';
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

// Chat functions
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    input.value = '';
    document.getElementById('send-btn').disabled = true;
    
    addMessage('user', message);
    
    try {
        const response = await fetch('/chat/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                question: message,
                top_k: 5
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addMessage('assistant', result.answer, result.sources);
        } else {
            addMessage('assistant', `Error: ${result.detail}`);
        }
    } catch (error) {
        addMessage('assistant', 'Sorry, there was a connection error. Please try again.');
    } finally {
        document.getElementById('send-btn').disabled = false;
    }
}

function addMessage(role, content, sources = null) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message-item ${role}-message`;
    
    let messageHTML = content;
    
    if (sources && sources.length > 0) {
        messageHTML += `
            <div class="sources">
                <strong>📚 Sources:</strong>
                ${sources.map(source => `
                    <div class="source-item">
                        <strong>${source.filename}</strong> (${(source.similarity * 100).toFixed(1)}% relevant)
                        <br><small>${source.content_preview}</small>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    messageDiv.innerHTML = messageHTML;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function loadChatHistory() {
    try {
        const response = await fetch('/chat/history?limit=20', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (result.history && result.history.length > 0) {
            const messagesContainer = document.getElementById('chat-messages');
            messagesContainer.innerHTML = '';
            
            result.history.forEach(item => {
                addMessage('user', item.message);
                addMessage('assistant', item.response, item.sources);
            });
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

async function clearChatHistory() {
    if (!confirm('Are you sure you want to clear your chat history?')) return;
    
    try {
        const response = await fetch('/chat/clear', {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            document.getElementById('chat-messages').innerHTML = '';
            addMessage('system', 'Chat history cleared successfully!');
        }
    } catch (error) {
        addMessage('system', 'Error clearing chat history. Please try again.');
    }
}

// Utility functions
function showMessage(message, type) {
    const messageEl = document.getElementById('auth-message');
    messageEl.textContent = message;
    messageEl.className = `message ${type}`;
    messageEl.style.display = 'block';
    
    setTimeout(() => {
        messageEl.style.display = 'none';
    }, 5000);
}

function hideMessage() {
    document.getElementById('auth-message').style.display = 'none';
}

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'flex' : 'none';
}
