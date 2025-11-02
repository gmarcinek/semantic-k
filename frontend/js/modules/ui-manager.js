/**
 * UI Manager for handling UI updates and interactions
 */
export class UIManager {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.typingIndicatorId = 'typingIndicator';
    }

    /**
     * Add a message to the chat
     * @param {string} role - Message role (user/assistant)
     * @param {string} content - Message content
     * @returns {HTMLElement} Message bubble element
     */
    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${role}`;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        try {
            bubbleDiv.innerHTML = window.DOMPurify ? DOMPurify.sanitize(content || '') : (content || '');
        } catch (e) {
            bubbleDiv.textContent = content || '';
        }

        messageDiv.appendChild(bubbleDiv);
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        return bubbleDiv;
    }

    /**
     * Add typing indicator
     */
    addTypingIndicator() {
        this.removeTypingIndicator();

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-assistant';
        messageDiv.id = this.typingIndicatorId;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';

        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';

        const dotsDiv = document.createElement('div');
        dotsDiv.className = 'typing-dots';
        dotsDiv.innerHTML = '<span></span><span></span><span></span>';

        const statusDiv = document.createElement('div');
        statusDiv.className = 'typing-status';
        statusDiv.textContent = 'Pracuje...';

        typingDiv.appendChild(dotsDiv);
        typingDiv.appendChild(statusDiv);
        bubbleDiv.appendChild(typingDiv);
        messageDiv.appendChild(bubbleDiv);

        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    /**
     * Remove typing indicator
     */
    removeTypingIndicator() {
        const indicator = document.getElementById(this.typingIndicatorId);
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Update typing indicator status message
     * @param {string} message - Status message
     */
    updateTypingStatus(message) {
        const statusEl = document.querySelector(`#${this.typingIndicatorId} .typing-status`);
        if (!statusEl) return;
        const hasMessage = typeof message === 'string' && message.trim().length > 0;
        statusEl.textContent = hasMessage ? message : 'Pracuje...';
        statusEl.style.display = hasMessage ? 'block' : 'none';
    }

    /**
     * Update metadata footer
     * @param {Object} metadata - Metadata object
     */
    updateMetadata(metadata) {
        const metaTopic = document.getElementById('metaTopic');
        const metaRelevance = document.getElementById('metaRelevance');
        const metaRelevanceText = document.getElementById('metaRelevanceText');
        const metaDanger = document.getElementById('metaDanger');
        const metaDangerText = document.getElementById('metaDangerText');
        const metaContinuation = document.getElementById('metaContinuation');
        const metaContinuationText = document.getElementById('metaContinuationText');
        const metaTopicChange = document.getElementById('metaTopicChange');
        const metaTopicChangeText = document.getElementById('metaTopicChangeText');
        const metaSummary = document.getElementById('metaSummary');

        // Topic
        const topicBadge = metadata.topic === 'GENERAL_KNOWLEDGE'
            ? `<span class="badge badge-general">📚 ${metadata.topic}</span>`
            : `<span class="badge badge-other">❓ ${metadata.topic}</span>`;
        metaTopic.innerHTML = topicBadge;

        // Relevance
        const relevancePercent = Math.round(metadata.topic_relevance * 100);
        metaRelevance.style.width = `${relevancePercent}%`;
        metaRelevanceText.textContent = `${relevancePercent}%`;

        // Danger
        const dangerPercent = Math.round(metadata.is_dangerous * 100);
        metaDanger.style.width = `${dangerPercent}%`;
        metaDangerText.textContent = `${dangerPercent}%`;

        // Continuation
        const continuationPercent = Math.round(metadata.is_continuation * 100);
        metaContinuation.style.width = `${continuationPercent}%`;
        metaContinuationText.textContent = `${continuationPercent}%`;

        // Topic Change
        const topicChangePercent = Math.round(metadata.topic_change * 100);
        metaTopicChange.style.width = `${topicChangePercent}%`;
        metaTopicChangeText.textContent = `${topicChangePercent}%`;

        // Summary
        metaSummary.textContent = metadata.summary;
    }

    /**
     * Setup auto-resize for a textarea element
     * @param {HTMLElement} element - Textarea element
     */
    setupAutoResize(element) {
        function resize() {
            element.style.height = 'auto';
            const max = 340;
            const h = Math.min(max, element.scrollHeight);
            element.style.height = h + 'px';
        }
        element.addEventListener('input', resize);
        resize();
    }

    /**
     * Scroll chat to bottom
     */
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    /**
     * Clear chat messages
     */
    clearChat() {
        this.chatMessages.innerHTML = `
            <div class="text-center text-muted">
                <p>👋 Witaj! Jestem asystentem Wikipedia Q&A.</p>
                <p>Zadaj mi pytanie, a znajdę dla Ciebie informacje z Wikipedii.</p>
            </div>
        `;
    }

    /**
     * Reset metadata display
     */
    resetMetadata() {
        const metaTopic = document.getElementById('metaTopic');
        const metaRelevance = document.getElementById('metaRelevance');
        const metaRelevanceText = document.getElementById('metaRelevanceText');
        const metaDanger = document.getElementById('metaDanger');
        const metaDangerText = document.getElementById('metaDangerText');
        const metaContinuation = document.getElementById('metaContinuation');
        const metaContinuationText = document.getElementById('metaContinuationText');
        const metaTopicChange = document.getElementById('metaTopicChange');
        const metaTopicChangeText = document.getElementById('metaTopicChangeText');
        const metaSummary = document.getElementById('metaSummary');

        metaTopic.textContent = '-';
        metaRelevance.style.width = '0%';
        metaRelevanceText.textContent = '0%';
        metaDanger.style.width = '0%';
        metaDangerText.textContent = '0%';
        metaContinuation.style.width = '0%';
        metaContinuationText.textContent = '0%';
        metaTopicChange.style.width = '0%';
        metaTopicChangeText.textContent = '0%';
        metaSummary.textContent = 'Oczekiwanie na pierwszą wiadomość...';
    }

    /**
     * Open image modal
     * @param {string} url - Image URL
     * @param {string} title - Image title
     */
    openImageModal(url, title) {
        try {
            const img = document.getElementById('imageModalImg');
            img.src = url;
            img.alt = title || '';
            const label = document.getElementById('imageModalLabel');
            label.textContent = title || 'Obraz';
            const modalEl = document.getElementById('imageModal');
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        } catch (e) {
            console.warn('openImageModal failed', e);
            window.open(url, '_blank');
        }
    }
}
