// Coach app — shared client (auth + API client + UI helpers).
//
// Auth: Google Identity Services. The ID token is stored in localStorage
// and sent on every API request as `Authorization: Bearer <token>`. Expired
// tokens (1h TTL) cause a 401, which redirects to login.html.

(function (global) {
    const TOKEN_KEY = 'sf-coach-id-token';
    const EMAIL_KEY = 'sf-coach-email';

    // Set in config.js (window.SAILFRAMES_COACH_API + window.SAILFRAMES_GOOGLE_CLIENT_ID).
    const API_BASE = (global.SAILFRAMES_COACH_API || '').replace(/\/+$/, '');
    const CLIENT_ID = global.SAILFRAMES_GOOGLE_CLIENT_ID || '';

    function getToken() { return localStorage.getItem(TOKEN_KEY); }
    function getEmail() { return localStorage.getItem(EMAIL_KEY); }
    function setSession(token, email) {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(EMAIL_KEY, email);
    }
    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(EMAIL_KEY);
    }
    function decodeIdToken(token) {
        try {
            const payload = token.split('.')[1];
            const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
            return JSON.parse(decodeURIComponent(escape(json)));
        } catch (e) {
            return null;
        }
    }

    function requireAuth() {
        const t = getToken();
        if (!t) { window.location.href = './login.html'; return false; }
        const claims = decodeIdToken(t);
        const expMs = claims && claims.exp ? claims.exp * 1000 : 0;
        if (!expMs || expMs < Date.now() + 30_000) {
            // Expired or about to expire — bounce.
            clearSession();
            window.location.href = './login.html';
            return false;
        }
        return true;
    }

    async function api(path, options = {}) {
        if (!API_BASE) {
            throw new Error('SAILFRAMES_COACH_API not configured (web/config.js).');
        }
        const token = getToken();
        const headers = { ...(options.headers || {}) };
        if (token) headers['Authorization'] = 'Bearer ' + token;
        if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
        const resp = await fetch(API_BASE + path, { ...options, headers });
        if (resp.status === 401) {
            clearSession();
            window.location.href = './login.html';
            throw new Error('unauthorized');
        }
        const text = await resp.text();
        let data;
        try { data = text ? JSON.parse(text) : null; } catch { data = text; }
        if (!resp.ok) {
            const msg = (data && data.detail) || (data && data.error) || resp.statusText;
            throw new Error(`API ${resp.status}: ${msg}`);
        }
        return data;
    }

    // Toast helper.
    function toast(msg, kind = 'info', ms = 3000) {
        let el = document.querySelector('.toast');
        if (!el) {
            el = document.createElement('div');
            el.className = 'toast';
            document.body.appendChild(el);
        }
        el.className = 'toast ' + kind;
        el.textContent = msg;
        // Force reflow so the transition runs from the start state.
        void el.offsetWidth;
        el.classList.add('show');
        clearTimeout(el._timer);
        el._timer = setTimeout(() => el.classList.remove('show'), ms);
    }

    // Render shared nav.
    function nav(crumbsHtml) {
        const me = getEmail() || '';
        const c = (crumbsHtml || '');
        return `
            <nav class="coach-nav">
                <a href="./index.html" class="brand">SailFrames Coach</a>
                <span class="crumbs">${c}</span>
                <div class="me">
                    <span>${me}</span>
                    <button id="coach-signout">Sign out</button>
                </div>
            </nav>
        `;
    }
    function wireNav() {
        const btn = document.getElementById('coach-signout');
        if (btn) btn.addEventListener('click', () => {
            clearSession();
            window.location.href = './login.html';
        });
    }

    // Format helpers — always render in browser-local time (no UTC anywhere).
    function fmtDate(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
        } catch { return iso; }
    }
    function fmtTimeLocal(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch { return iso; }
    }
    function fmtTimeShortLocal(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
        } catch { return iso; }
    }
    // Reviewer-email → human name (extend as needed).
    const REVIEWER_NAMES = {
        'avillach@gmail.com': 'Paul Avillach',
        'gordonparris1983@gmail.com': 'Gordon Parris',
    };
    function reviewerName(email) {
        if (!email) return '—';
        return REVIEWER_NAMES[email.toLowerCase()] || email;
    }

    global.SailFramesCoach = {
        CLIENT_ID,
        getToken, getEmail, setSession, clearSession,
        requireAuth, api, toast, nav, wireNav,
        fmtDate, fmtTimeLocal, fmtTimeShortLocal, reviewerName,
        decodeIdToken,
    };
})(window);
