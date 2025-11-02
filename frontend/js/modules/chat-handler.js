/**
 * Chat Handler for managing chat interactions
 */
export class ChatHandler {
    constructor(apiClient, uiManager, stateManager, articlesManager) {
        this.apiClient = apiClient;
        this.uiManager = uiManager;
        this.stateManager = stateManager;
        this.articlesManager = articlesManager;

        // Store reference to session ID in API client for articles manager
        this._setupApiClientSessionId();
    }

    /**
     * Setup session ID reference in API client
     */
    _setupApiClientSessionId() {
        Object.defineProperty(this.apiClient, 'sessionId', {
            get: () => this.stateManager.sessionId
        });
    }

    /**
     * Send chat message
     * @param {string} prompt - User prompt
     */
    async sendMessage(prompt) {
        if (!prompt.trim() || this.stateManager.isProcessing) return;

        this.stateManager.isProcessing = true;
        this._setInputsDisabled(true);

        // Add user message to chat
        this.uiManager.addMessage('user', prompt);

        // Clear input
        const userPromptInput = document.getElementById('userPrompt');
        userPromptInput.value = '';

        // Add typing indicator
        this.uiManager.addTypingIndicator();

        try {
            const response = await this.apiClient.sendMessage(prompt, this.stateManager.sessionId);

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            await this._processStreamResponse(response);

        } catch (error) {
            console.error('Error:', error);
            this.uiManager.removeTypingIndicator();
            this.uiManager.addMessage('assistant', '❌ Wystąpił błąd podczas przetwarzania wiadomości.');
        } finally {
            this.stateManager.isProcessing = false;
            this._setInputsDisabled(false);
            document.getElementById('userPrompt').focus();
        }
    }

    /**
     * Reset chat session
     */
    async resetSession() {
        if (this.stateManager.isProcessing) return;

        try {
            const data = await this.apiClient.resetSession(this.stateManager.sessionId);
            this.stateManager.sessionId = data.session_id;

            // Clear chat messages
            this.uiManager.clearChat();

            // Clear articles list
            this.articlesManager.clearArticles();

            // Reset metadata
            this.uiManager.resetMetadata();

            document.getElementById('userPrompt').focus();
        } catch (error) {
            console.error('Error resetting session:', error);
            alert('Wystąpił błąd podczas resetowania sesji.');
        }
    }

    /**
     * Research a Wikipedia article
     * @param {number} pageid - Wikipedia page ID
     * @param {string} title - Article title
     */
    async researchArticle(pageid, title) {
        if (this.stateManager.isProcessing) return;

        try {
            this.stateManager.isProcessing = true;
            this._setInputsDisabled(true);
            this.uiManager.addTypingIndicator();

            const response = await this.apiClient.researchArticle(pageid, title, this.stateManager.sessionId);

            if (!response.ok) throw new Error('Network response was not ok');

            await this._processStreamResponse(response);

        } catch (err) {
            console.error('Research error', err);
            this.uiManager.removeTypingIndicator();
            this.uiManager.addMessage('assistant', '❌ Błąd podczas badania artykułu.');
        } finally {
            this.stateManager.isProcessing = false;
            this._setInputsDisabled(false);
            document.getElementById('userPrompt').focus();
        }
    }

    /**
     * Process streaming response from server
     * @param {Response} response - Fetch response
     */
    async _processStreamResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = null;
        let fullResponse = '';
        let pendingGalleryData = null;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'metadata') {
                        this.uiManager.updateMetadata(data.data);
                    } else if (data.type === 'status') {
                        const statusMessage = typeof data.data === 'string'
                            ? data.data
                            : (data.data && data.data.message) || '';
                        this.uiManager.updateTypingStatus(statusMessage);
                    } else if (data.type === 'wikipedia') {
                        this.articlesManager.addArticlesToLeftColumn(data.data);
                        pendingGalleryData = data.data;
                    } else if (data.type === 'chunk') {
                        // Remove typing indicator on first chunk
                        if (!assistantMessage) {
                            this.uiManager.removeTypingIndicator();
                            assistantMessage = this.uiManager.addMessage('assistant', '');
                        }
                        fullResponse += data.data;
                        try {
                            assistantMessage.innerHTML = window.DOMPurify ? DOMPurify.sanitize(fullResponse) : fullResponse;
                        } catch (_) {
                            assistantMessage.textContent = fullResponse;
                        }
                        this.uiManager.scrollToBottom();
                    } else if (data.type === 'done') {
                        this.uiManager.removeTypingIndicator();
                        if (pendingGalleryData) {
                            this.articlesManager.appendWikipediaImageGallery(assistantMessage, pendingGalleryData);
                            pendingGalleryData = null;
                        }
                    } else if (data.type === 'error') {
                        this.uiManager.removeTypingIndicator();
                        if (!assistantMessage) {
                            assistantMessage = this.uiManager.addMessage('assistant', '');
                        }
                        try {
                            assistantMessage.innerHTML = window.DOMPurify ? DOMPurify.sanitize('❌ ' + data.data) : ('❌ ' + data.data);
                        } catch (_) {
                            assistantMessage.textContent = '❌ ' + data.data;
                        }
                        assistantMessage.style.color = '#dc3545';
                    }
                }
            }
        }
    }

    /**
     * Set input elements disabled state
     * @param {boolean} disabled - Disabled state
     */
    _setInputsDisabled(disabled) {
        const sendBtn = document.getElementById('sendBtn');
        const userPromptInput = document.getElementById('userPrompt');
        sendBtn.disabled = disabled;
        userPromptInput.disabled = disabled;
    }
}
