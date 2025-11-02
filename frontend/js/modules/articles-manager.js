/**
 * Articles Manager for managing Wikipedia articles in the left sidebar
 */
export class ArticlesManager {
    constructor(apiClient, uiManager) {
        this.apiClient = apiClient;
        this.uiManager = uiManager;
        this.articlesList = document.getElementById('articlesList');
    }

    /**
     * Add articles to left column
     * @param {Object} wikipediaData - Wikipedia data with sources
     */
    addArticlesToLeftColumn(wikipediaData) {
        if (!wikipediaData || !wikipediaData.sources || !Array.isArray(wikipediaData.sources)) {
            return;
        }

        // Clear "no articles" placeholder if present
        if (this.articlesList.querySelector('.text-center.text-muted')) {
            this.articlesList.innerHTML = '';
        }

        const contextTopics = Array.isArray(wikipediaData.context_topics) ? wikipediaData.context_topics : [];
        const primaryPageId = typeof wikipediaData.primary_pageid === 'number' ? wikipediaData.primary_pageid : null;

        wikipediaData.sources.forEach((source) => {
            // Check if article already exists in the list
            const existingArticle = this.articlesList.querySelector(`[data-pageid="${source.pageid}"]`);
            if (existingArticle) {
                return; // Skip if already added
            }

            const articleItem = this._createArticleElement(source, contextTopics, primaryPageId);
            this.articlesList.appendChild(articleItem);
        });
    }

    /**
     * Create article element
     * @param {Object} source - Article source
     * @param {Array} contextTopics - Context topics
     * @param {number} primaryPageId - Primary page ID
     * @returns {HTMLElement} Article element
     */
    _createArticleElement(source, contextTopics, primaryPageId) {
        const articleItem = document.createElement('div');
        articleItem.className = 'article-item';
        articleItem.setAttribute('data-pageid', source.pageid);

        // Header with title and remove button
        const headerDiv = this._createArticleHeader(source);
        articleItem.appendChild(headerDiv);

        // Role badges (PRIMARY or CONTEXT)
        this._addRoleBadge(articleItem, source, contextTopics, primaryPageId);

        // Relevance score
        this._addRelevanceScore(articleItem, source);

        // Extract/snippet
        this._addExtract(articleItem, source);

        // Images
        this._addImages(articleItem, source);

        // Action buttons
        const actionsDiv = this._createActionButtons(source);
        articleItem.appendChild(actionsDiv);

        return articleItem;
    }

    /**
     * Create article header with title and remove button
     * @param {Object} source - Article source
     * @returns {HTMLElement} Header element
     */
    _createArticleHeader(source) {
        const headerDiv = document.createElement('div');
        headerDiv.className = 'article-item-header';

        const titleLink = document.createElement('a');
        titleLink.href = source.url;
        titleLink.target = '_blank';
        titleLink.className = 'article-item-title';
        titleLink.textContent = source.title;

        const removeBtn = document.createElement('button');
        removeBtn.className = 'article-item-remove';
        removeBtn.textContent = 'Usuń';
        removeBtn.addEventListener('click', () => this.removeArticle(source.pageid));

        headerDiv.appendChild(titleLink);
        headerDiv.appendChild(removeBtn);
        return headerDiv;
    }

    /**
     * Add role badge to article
     * @param {HTMLElement} articleItem - Article element
     * @param {Object} source - Article source
     * @param {Array} contextTopics - Context topics
     * @param {number} primaryPageId - Primary page ID
     */
    _addRoleBadge(articleItem, source, contextTopics, primaryPageId) {
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
            roleBadge.className = `badge ${isPrimary ? 'badge-role-primary' : 'badge-role-context'} me-1`;
            roleBadge.textContent = isPrimary ? 'GŁÓWNE HASŁO' : 'KONTEKST';
            roleBadge.style.fontSize = '0.7rem';
            articleItem.appendChild(roleBadge);
        }
    }

    /**
     * Add relevance score to article
     * @param {HTMLElement} articleItem - Article element
     * @param {Object} source - Article source
     */
    _addRelevanceScore(articleItem, source) {
        if (source.relevance_score !== null && source.relevance_score !== undefined) {
            const relevanceDiv = document.createElement('div');
            relevanceDiv.className = 'article-item-relevance';
            const rel = Math.round(source.relevance_score * 100);
            relevanceDiv.textContent = `Relevance: ${rel}%`;
            articleItem.appendChild(relevanceDiv);
        }
    }

    /**
     * Add extract to article
     * @param {HTMLElement} articleItem - Article element
     * @param {Object} source - Article source
     */
    _addExtract(articleItem, source) {
        if (source.extract) {
            const extractDiv = document.createElement('div');
            extractDiv.className = 'article-item-extract';
            const excerpt = source.extract.length > 150 ? `${source.extract.substring(0, 150)}…` : source.extract;
            extractDiv.textContent = excerpt;
            articleItem.appendChild(extractDiv);
        }
    }

    /**
     * Add images to article
     * @param {HTMLElement} articleItem - Article element
     * @param {Object} source - Article source
     */
    _addImages(articleItem, source) {
        const images = Array.isArray(source.images) ? source.images : (source.image_url ? [source.image_url] : []);
        if (images.length > 0) {
            const imagesDiv = document.createElement('div');
            imagesDiv.className = 'article-item-images';
            images.slice(0, 3).forEach((url) => { // Limit to 3 images in sidebar
                const thumb = document.createElement('img');
                thumb.src = url;
                thumb.alt = source.title;
                thumb.addEventListener('click', () => this.uiManager.openImageModal(url, source.title));
                imagesDiv.appendChild(thumb);
            });
            articleItem.appendChild(imagesDiv);
        }
    }

    /**
     * Create action buttons for article
     * @param {Object} source - Article source
     * @returns {HTMLElement} Actions element
     */
    _createActionButtons(source) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'article-item-actions';

        const exploreBtn = document.createElement('button');
        exploreBtn.className = 'btn btn-primary btn-sm';
        exploreBtn.textContent = 'Zbadaj';
        exploreBtn.addEventListener('click', () => {
            // This will be handled by ChatHandler
            window.dispatchEvent(new CustomEvent('research-article', {
                detail: { pageid: source.pageid, title: source.title }
            }));
        });

        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn btn-secondary btn-sm';
        viewBtn.textContent = 'Zobacz';
        viewBtn.addEventListener('click', () => {
            window.open(source.url, '_blank');
        });

        actionsDiv.appendChild(exploreBtn);
        actionsDiv.appendChild(viewBtn);
        return actionsDiv;
    }

    /**
     * Remove article from session and UI
     * @param {number} pageid - Wikipedia page ID
     */
    async removeArticle(pageid) {
        try {
            const result = await this.apiClient.removeArticle(pageid, this.apiClient.sessionId);

            if (result.success) {
                // Remove from UI
                const articleItem = this.articlesList.querySelector(`[data-pageid="${pageid}"]`);
                if (articleItem) {
                    articleItem.remove();
                }

                // If no articles left, show placeholder
                if (this.articlesList.children.length === 0) {
                    this.clearArticles();
                }
            } else {
                console.error('Failed to remove article:', result.message);
            }
        } catch (error) {
            console.error('Error removing article:', error);
        }
    }

    /**
     * Clear all articles and show placeholder
     */
    clearArticles() {
        this.articlesList.innerHTML = `
            <div class="text-center text-muted p-3">
                <p>Brak artykułów</p>
                <small>Artykuły Wikipedii pojawią się tutaj po zadaniu pytania</small>
            </div>
        `;
    }

    /**
     * Append Wikipedia image gallery (legacy support)
     * @param {HTMLElement} targetBubble - Target message bubble
     * @param {Object} wikipediaData - Wikipedia data
     */
    appendWikipediaImageGallery(targetBubble, wikipediaData) {
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
                img.style.maxWidth = '180px';
                img.style.maxHeight = '180px';
                img.style.height = 'auto';
                img.style.width = 'auto';
                img.style.borderRadius = '6px';
                img.style.border = '1px solid rgba(0,0,0,0.1)';
                img.style.cursor = 'pointer';
                img.addEventListener('click', () => this.uiManager.openImageModal(url, title));
                gallery.appendChild(img);
            });

            if (targetBubble && targetBubble.parentElement) {
                targetBubble.parentElement.appendChild(gallery);
            } else {
                document.getElementById('chatMessages').appendChild(gallery);
            }
        } catch (e) {
            console.warn('appendWikipediaImageGallery failed', e);
        }
    }
}
