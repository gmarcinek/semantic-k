// Global state
let sessionId = generateUUID();
let isProcessing = false;

// DOM elements
const chatForm = document.getElementById('chatForm');
const userPromptInput = document.getElementById('userPrompt');
const chatMessages = document.getElementById('chatMessages');
const sendBtn = document.getElementById('sendBtn');
const resetBtn = document.getElementById('resetBtn');

// Metadata elements
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

// Generate UUID
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Auto-resize textarea up to 340px
function setupAutoResize(el) {
    function resize() {
        el.style.height = 'auto';
        const max = 340;
        const h = Math.min(max, el.scrollHeight);
        el.style.height = h + 'px';
    }
    el.addEventListener('input', resize);
    // Initialize once
    resize();
}
setupAutoResize(userPromptInput);

// Add message to chat
function addMessage(role, content) {
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
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return bubbleDiv;
}

// Add typing indicator
function addTypingIndicator() {
    removeTypingIndicator();

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-assistant';
    messageDiv.id = 'typingIndicator';

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

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Update typing indicator status text
function updateTypingStatus(message) {
    const statusEl = document.querySelector('#typingIndicator .typing-status');
    if (!statusEl) return;
    const hasMessage = typeof message === 'string' && message.trim().length > 0;
    statusEl.textContent = hasMessage ? message : 'Pracuje...';
    statusEl.style.display = hasMessage ? 'block' : 'none';
}

// Update metadata footer
function updateMetadata(metadata) {
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

// Display Wikipedia sources
function displayWikipediaSources(wikipediaData) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'wikipedia-sources';

    const rerankInfo = wikipediaData.reranked && wikipediaData.reranking_model ? `, reranked by ${wikipediaData.reranking_model}` : '';
    const title = document.createElement('h6');
    title.textContent = `Wikipedia Sources (${wikipediaData.sources.length} articles${rerankInfo}):`;

    if (wikipediaData.primary_topic) {
        const primaryBadge = document.createElement('span');
        primaryBadge.className = 'badge badge-role-primary ms-2';
        primaryBadge.textContent = `Glowne haslo: ${wikipediaData.primary_topic}`;
        title.appendChild(document.createTextNode(' '));
        title.appendChild(primaryBadge);
    }

    sourcesDiv.appendChild(title);

    if (wikipediaData.intent_notes) {
        const note = document.createElement('div');
        note.className = 'source-intent-note';
        note.textContent = wikipediaData.intent_notes;
        sourcesDiv.appendChild(note);
    }

    const contextTopics = Array.isArray(wikipediaData.context_topics) ? wikipediaData.context_topics : [];
    const primaryPageId = typeof wikipediaData.primary_pageid === 'number' ? wikipediaData.primary_pageid : null;

    wikipediaData.sources.forEach((source, index) => {
        const sourceItem = document.createElement('div');
        sourceItem.className = 'source-item';

        const headerDiv = document.createElement('div');
        headerDiv.style.display = 'flex';
        headerDiv.style.flexWrap = 'wrap';
        headerDiv.style.alignItems = 'center';
        headerDiv.style.gap = '0.5rem';

        const titleLink = document.createElement('a');
        titleLink.href = source.url;
        titleLink.target = '_blank';
        titleLink.className = 'source-title';
        titleLink.textContent = `${index + 1}. ${source.title}`;
        headerDiv.appendChild(titleLink);

        const sourcePageId = typeof source.pageid === 'number' ? source.pageid : (source.pageid ? Number(source.pageid) : null);
        const isPrimary = primaryPageId !== null && sourcePageId !== null && primaryPageId === sourcePageId;
        const contextMatch = contextTopics.find(ctx => {
            const ctxPageId = typeof ctx.pageid === 'number' ? ctx.pageid : (ctx.pageid ? Number(ctx.pageid) : null);
            if (ctxPageId && sourcePageId) {
                return ctxPageId === sourcePageId;
            }
            if (ctx.title && source.title) {
                return ctx.title.toLowerCase() === source.title.toLowerCase();
            }
            return false;
        });

        if (isPrimary || contextMatch) {
            const roleBadge = document.createElement('span');
            roleBadge.className = `badge ${isPrimary ? 'badge-role-primary' : 'badge-role-context'}`;
            roleBadge.textContent = isPrimary ? 'GLOWNE HASLO' : 'KONTEKST';
            headerDiv.appendChild(roleBadge);
        }

        if (source.relevance_score !== null && source.relevance_score !== undefined) {
            const relevanceSpan = document.createElement('span');
            relevanceSpan.className = 'source-relevance';
            const rel = Math.round(source.relevance_score * 100);
            relevanceSpan.textContent = `(Relevance: ${rel}%)`;
            headerDiv.appendChild(relevanceSpan);
        }

        sourceItem.appendChild(headerDiv);

        if (contextMatch && contextMatch.reasoning) {
            const reasoning = document.createElement('div');
            reasoning.className = 'source-intent-note';
            reasoning.textContent = contextMatch.reasoning;
            sourceItem.appendChild(reasoning);
        }

        const images = Array.isArray(source.images) ? source.images : (source.image_url ? [source.image_url] : []);
        if (images.length > 0) {
            const gallery = document.createElement('div');
            gallery.style.display = 'flex';
            gallery.style.flexWrap = 'wrap';
            gallery.style.gap = '8px';
            gallery.style.marginTop = '6px';
            images.forEach((url) => {
                const thumb = document.createElement('img');
                thumb.src = url;
                thumb.alt = source.title;
                thumb.style.maxHeight = '180px';
                thumb.style.maxWidth = '180px';
                thumb.style.height = 'auto';
                thumb.style.width = 'auto';
                thumb.style.borderRadius = '6px';
                thumb.style.border = '1px solid rgba(0,0,0,0.1)';
                thumb.style.cursor = 'pointer';
                thumb.addEventListener('click', () => openImageModal(url, source.title));
                gallery.appendChild(thumb);
            });
            sourceItem.appendChild(gallery);
        }

        if (source.extract) {
            const extractDiv = document.createElement('div');
            extractDiv.className = 'source-extract';
            const excerpt = source.extract.length > 150 ? `${source.extract.substring(0, 150)}…` : source.extract;
            extractDiv.textContent = excerpt;
            sourceItem.appendChild(extractDiv);
        }

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'source-actions';

        const exploreBtn = document.createElement('button');
        exploreBtn.className = 'btn btn-primary btn-xs';
        exploreBtn.textContent = 'Zbadaj';
        exploreBtn.addEventListener('click', () => {
            researchArticle(source.pageid, source.title);
        });

        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn btn-secondary btn-xs';
        viewBtn.textContent = 'Zobacz';
        viewBtn.addEventListener('click', () => {
            window.open(source.url, '_blank');
        });

        actionsDiv.appendChild(exploreBtn);
        actionsDiv.appendChild(viewBtn);
        sourceItem.appendChild(actionsDiv);

        sourcesDiv.appendChild(sourceItem);
    });

    chatMessages.appendChild(sourcesDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Helper: append image gallery under a message bubble
function appendWikipediaImageGallery(targetBubble, wikipediaData) {
    try {
        if (!wikipediaData || !Array.isArray(wikipediaData.sources)) return;
        const withImgs = wikipediaData.sources.filter(s => s && (s.images && s.images.length || s.image_url));
        if (withImgs.length === 0) return;
        const gallery = document.createElement('div');
        gallery.className = 'wiki-image-gallery';
        gallery.style.display = 'flex';
        gallery.style.flexWrap = 'wrap';
        gallery.style.gap = '8px';
        gallery.style.marginTop = '8px';
        const urls = [];
        withImgs.forEach(s => {
            if (Array.isArray(s.images) && s.images.length) {
                s.images.forEach(u => urls.push({ url: u, title: s.title }));
            } else if (s.image_url) {
                urls.push({ url: s.image_url, title: s.title });
            }
        });
        urls.forEach(({url, title}) => {
            const img = document.createElement('img');
            img.src = url;
            img.alt = title;
            img.style.maxWidth = '300px';
            img.style.height = 'auto';
            img.style.borderRadius = '6px';
            img.style.border = '1px solid rgba(0,0,0,0.1)';
            img.style.cursor = 'pointer';
            img.addEventListener('click', () => openImageModal(url, title));
            gallery.appendChild(img);
        });
        if (targetBubble && targetBubble.parentElement) {
            targetBubble.parentElement.appendChild(gallery);
        } else {
            chatMessages.appendChild(gallery);
        }
    } catch (e) {
        console.warn('appendWikipediaImageGallery failed', e);
    }
}

// Research a full article and stream assistant summary
async function researchArticle(pageid, title) {
    if (isProcessing) return;

    try {
        isProcessing = true;
        sendBtn.disabled = true;
        userPromptInput.disabled = true;
        addTypingIndicator();

        const response = await fetch('/api/wiki/research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, pageid: pageid, title: title })
        });

        if (!response.ok) throw new Error('Network response was not ok');

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
                    if (data.type === 'wikipedia') {
                        pendingGalleryData = data.data;
                    } else if (data.type === 'status') {
                        const statusMessage = typeof data.data === 'string'
                            ? data.data
                            : (data.data && data.data.message) || '';
                        updateTypingStatus(statusMessage);
                    } else if (data.type === 'chunk') {
                        if (!assistantMessage) {
                            removeTypingIndicator();
                            assistantMessage = addMessage('assistant', '');
                        }
                        fullResponse += data.data;
                        try {
                            assistantMessage.innerHTML = window.DOMPurify ? DOMPurify.sanitize(fullResponse) : fullResponse;
                        } catch (_) {
                            assistantMessage.textContent = fullResponse;
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    } else if (data.type === 'done') {
                        removeTypingIndicator();
                        if (pendingGalleryData) {
                            appendWikipediaImageGallery(assistantMessage, pendingGalleryData);
                            pendingGalleryData = null;
                        }
                    } else if (data.type === 'error') {
                        removeTypingIndicator();
                        if (!assistantMessage) assistantMessage = addMessage('assistant', '');
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
    } catch (err) {
        console.error('Research error', err);
        removeTypingIndicator();
        addMessage('assistant', '❌ Błąd podczas badania artykułu.');
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        userPromptInput.disabled = false;
        userPromptInput.focus();
    }
}

// Send chat message
async function sendMessage(prompt) {
    if (!prompt.trim() || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;
    userPromptInput.disabled = true;

    // Add user message to chat
    addMessage('user', prompt);

    // Clear input
    userPromptInput.value = '';

    // Add typing indicator
    addTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = null;
        let fullResponse = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'metadata') {
                        updateMetadata(data.data);
                    } else if (data.type === 'status') {
                        const statusMessage = typeof data.data === 'string'
                            ? data.data
                            : (data.data && data.data.message) || '';
                        updateTypingStatus(statusMessage);
                    } else if (data.type === 'wikipedia') {
                        displayWikipediaSources(data.data);
                        pendingGalleryData = data.data;
                    } else if (data.type === 'chunk') {
                        // Remove typing indicator on first chunk
                        if (!assistantMessage) {
                            removeTypingIndicator();
                            assistantMessage = addMessage('assistant', '');
                        }
                        fullResponse += data.data;
                        try {
                            assistantMessage.innerHTML = window.DOMPurify ? DOMPurify.sanitize(fullResponse) : fullResponse;
                        } catch (_) {
                            assistantMessage.textContent = fullResponse;
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    } else if (data.type === 'done') {
                        removeTypingIndicator();
                        if (pendingGalleryData) {
                            appendWikipediaImageGallery(assistantMessage, pendingGalleryData);
                            pendingGalleryData = null;
                        }
                    } else if (data.type === 'error') {
                        removeTypingIndicator();
                        if (!assistantMessage) {
                            assistantMessage = addMessage('assistant', '');
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
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator();
        addMessage('assistant', '❌ Wystąpił błąd podczas przetwarzania wiadomości.');
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        userPromptInput.disabled = false;
        userPromptInput.focus();
    }
}

// Reset chat session
async function resetSession() {
    if (isProcessing) return;

    try {
        const response = await fetch('/api/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        if (response.ok) {
            const data = await response.json();
            sessionId = data.session_id;

            // Clear chat messages
            chatMessages.innerHTML = `
                <div class="text-center text-muted">
                    <p>👋 Witaj! Jestem asystentem Wikipedia Q&A.</p>
                    <p>Zadaj mi pytanie, a znajdę dla Ciebie informacje z Wikipedii.</p>
                </div>
            `;

            // Reset metadata
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

            userPromptInput.focus();
        }
    } catch (error) {
        console.error('Error resetting session:', error);
        alert('Wystąpił błąd podczas resetowania sesji.');
    }
}

// Event listeners
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const prompt = userPromptInput.value.trim();
    if (prompt) {
        sendMessage(prompt);
    }
});

resetBtn.addEventListener('click', resetSession);

// Allow Ctrl+Enter to send message
userPromptInput.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        const prompt = userPromptInput.value.trim();
        if (prompt && !isProcessing) {
            sendMessage(prompt);
        }
    }
});

// Focus on input on load
userPromptInput.focus();

// Bootstrap image modal helper
function openImageModal(url, title) {
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
