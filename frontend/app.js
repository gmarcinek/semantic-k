/**
 * Main application file - Refactored with modular architecture
 */
import { ApiClient } from './js/modules/api.js';
import { UIManager } from './js/modules/ui-manager.js';
import { ChatHandler } from './js/modules/chat-handler.js';
import { StateManager } from './js/modules/state-manager.js';
import { ArticlesManager } from './js/modules/articles-manager.js';

// Initialize services
const stateManager = new StateManager();
const apiClient = new ApiClient();
const uiManager = new UIManager();
const articlesManager = new ArticlesManager(apiClient, uiManager);
const chatHandler = new ChatHandler(apiClient, uiManager, stateManager, articlesManager);

// DOM elements
const chatForm = document.getElementById('chatForm');
const userPromptInput = document.getElementById('userPrompt');
const resetBtn = document.getElementById('resetBtn');

// Setup auto-resize for textarea
uiManager.setupAutoResize(userPromptInput);

// Event listeners
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const prompt = userPromptInput.value.trim();
    if (prompt) {
        chatHandler.sendMessage(prompt);
    }
});

resetBtn.addEventListener('click', () => chatHandler.resetSession());

// Allow Ctrl+Enter to send message
userPromptInput.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        const prompt = userPromptInput.value.trim();
        if (prompt && !stateManager.isProcessing) {
            chatHandler.sendMessage(prompt);
        }
    }
});

// Handle research article events from articles manager
window.addEventListener('research-article', (e) => {
    const { pageid, title } = e.detail;
    chatHandler.researchArticle(pageid, title);
});

// Focus on input on load
userPromptInput.focus();
