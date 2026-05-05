// Collapsible chat panel for race.html. Streams from the SailFrames
// chat Lambda (Function URL). Conversation lives in memory only;
// refresh = new chat.
//
// Wiring: race-app.js calls SailFramesChat.attach(getCtx) once after
// the race has loaded, where getCtx() returns the in-memory state
// SailFramesBriefing.build expects. The chat panel rebuilds the
// briefing on each turn from getCtx() so it always reflects current
// dashboard state (e.g. if the user changes wind source).

(function () {
  'use strict';

  const NS = (window.SailFramesChat = window.SailFramesChat || {});
  // Default endpoint = the prod HTTP API; override via window.SAILFRAMES_CHAT_URL.
  const ENDPOINT = window.SAILFRAMES_CHAT_URL ||
    'https://rnngzx7flk.execute-api.us-east-1.amazonaws.com/api/chat';

  let panelEl = null;
  let logEl = null;
  let inputEl = null;
  let boatSelectEl = null;
  let getCtx = null;
  const messages = [];        // { role, content }
  let streaming = false;

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function build(ctx) {
    const root = el('div', 'sf-chat-root');
    root.innerHTML = `
      <button class="sf-chat-toggle" aria-label="Race coach">Race coach</button>
      <div class="sf-chat-panel" hidden>
        <div class="sf-chat-header">
          <strong>Race coach</strong>
          <label class="sf-chat-asas">
            <span>I am</span>
            <select class="sf-chat-boat">
              <option value="">a spectator</option>
            </select>
          </label>
          <button class="sf-chat-close" aria-label="Close">×</button>
        </div>
        <div class="sf-chat-log"></div>
        <form class="sf-chat-input-row">
          <input type="text" class="sf-chat-input"
                 placeholder="Ask anything about this race…" autocomplete="off">
          <button type="submit" class="sf-chat-send">Send</button>
        </form>
        <div class="sf-chat-foot">Answers come from race data only.
          Powered by Claude. Be patient with long questions.</div>
      </div>`;
    document.body.appendChild(root);

    panelEl = root.querySelector('.sf-chat-panel');
    logEl = root.querySelector('.sf-chat-log');
    inputEl = root.querySelector('.sf-chat-input');
    boatSelectEl = root.querySelector('.sf-chat-boat');

    root.querySelector('.sf-chat-toggle').onclick = () => {
      panelEl.hidden = !panelEl.hidden;
      if (!panelEl.hidden) inputEl.focus();
    };
    root.querySelector('.sf-chat-close').onclick = () => { panelEl.hidden = true; };
    root.querySelector('.sf-chat-input-row').onsubmit = (e) => {
      e.preventDefault();
      send(inputEl.value);
    };

    // Populate boat dropdown from the current ctx fleet.
    const c = getCtx();
    for (const id of Object.keys(c.boats || {})) {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = `skipper of ${c.boats[id].hull || id}`;
      boatSelectEl.appendChild(opt);
    }
  }

  function pushMessage(role, text) {
    const m = el('div', `sf-chat-msg sf-chat-msg-${role}`);
    m.textContent = text;
    logEl.appendChild(m);
    logEl.scrollTop = logEl.scrollHeight;
    return m;
  }

  async function send(text) {
    text = (text || '').trim();
    if (!text || streaming) return;
    streaming = true;
    inputEl.value = '';
    pushMessage('user', text);
    messages.push({ role: 'user', content: text });

    const replyEl = pushMessage('assistant', '');
    replyEl.textContent = '…';
    let buf = '';

    const ctx = getCtx();
    const briefing = window.SailFramesBriefing.build(ctx);

    try {
      const resp = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          race_briefing: briefing,
          user_boat: boatSelectEl.value || null,
          messages: messages,
        }),
      });
      if (!resp.ok) {
        const errBody = await resp.text();
        replyEl.textContent = `Error: HTTP ${resp.status} ${errBody.slice(0, 200)}`;
        streaming = false;
        return;
      }
      const data = await resp.json();
      buf = data.text || '';
      replyEl.textContent = buf || '(no response)';
      messages.push({ role: 'assistant', content: buf });
    } catch (e) {
      replyEl.textContent = `Error: ${e.message}`;
    } finally {
      streaming = false;
    }
  }

  /**
   * @param {function():object} contextFn  returns the current dashboard
   *   state for SailFramesBriefing.build (currentRace, boats, legRows,
   *   maneuvers, windSamples, windSource, finishOrder).
   */
  NS.attach = function (contextFn) {
    getCtx = contextFn;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => build());
    } else {
      build();
    }
  };
})();
