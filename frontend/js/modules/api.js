/**
 * API Client for backend communication
 */
export class ApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    /**
     * Send a chat message
     * @param {string} prompt - User prompt
     * @param {string} sessionId - Session ID
     * @returns {Promise<Response>} Fetch response
     */
    async sendMessage(prompt, sessionId) {
        return await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt,
                session_id: sessionId
            })
        });
    }

    /**
     * Reset chat session
     * @param {string} sessionId - Session ID to reset
     * @returns {Promise<Object>} Response data
     */
    async resetSession(sessionId) {
        const response = await fetch('/api/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });
        return await response.json();
    }

    /**
     * Research a Wikipedia article
     * @param {number} pageid - Wikipedia page ID
     * @param {string} title - Article title
     * @param {string} sessionId - Session ID
     * @returns {Promise<Response>} Fetch response
     */
    async researchArticle(pageid, title, language, sessionId) {
        return await fetch('/api/wiki/research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                pageid: pageid,
                title: title,
                language: language
            })
        });
    }

    /**
     * Remove an article from session
     * @param {number} pageid - Wikipedia page ID
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Response data
     */
    async removeArticle(pageid, sessionId) {
        const response = await fetch('/api/articles/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                pageid: pageid
            })
        });
        return await response.json();
    }

    /**
     * Get articles for a session
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Response data
     */
    async getArticles(sessionId) {
        const response = await fetch(`/api/articles/${sessionId}`);
        return await response.json();
    }
}
