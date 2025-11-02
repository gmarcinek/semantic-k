/**
 * State Manager for managing application state
 */
export class StateManager {
    constructor() {
        this._sessionId = this.generateUUID();
        this._isProcessing = false;
    }

    /**
     * Get session ID
     * @returns {string}
     */
    get sessionId() {
        return this._sessionId;
    }

    /**
     * Set session ID
     * @param {string} value - New session ID
     */
    set sessionId(value) {
        this._sessionId = value;
    }

    /**
     * Get processing state
     * @returns {boolean}
     */
    get isProcessing() {
        return this._isProcessing;
    }

    /**
     * Set processing state
     * @param {boolean} value - Processing state
     */
    set isProcessing(value) {
        this._isProcessing = value;
    }

    /**
     * Generate UUID for session
     * @returns {string} UUID
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
}
