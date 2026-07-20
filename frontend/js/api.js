/* ==========================================================================
   api.js — fetch wrappers + SSE stream parser (no dependencies)
   ========================================================================== */
(function (global) {
  'use strict';

  const BASE = (global.API_BASE_URL || `${location.protocol}//${location.hostname}${location.port ? ':' + location.port : ''}`);

  /* ----- helpers ------------------------------------------------------- */
  async function jsonFetch(url, opts = {}) {
    const init = Object.assign(
      { headers: { 'Content-Type': 'application/json' } },
      opts
    );
    if (opts.body && typeof opts.body !== 'string') {
      init.body = JSON.stringify(opts.body);
    }
    let resp;
    try {
      resp = await fetch(url, init);
    } catch (e) {
      throw new Error('网络异常：' + (e.message || e));
    }
    const text = await resp.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }
    if (!resp.ok) {
      const msg = (data && (data.detail || data.error || data.message))
        || `HTTP ${resp.status}`;
      const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  /* ----- SSE parser ---------------------------------------------------- */
  /**
   * parseSSEStream(reader, onEvent)
   * - reader: a ReadableStreamDefaultReader of Uint8Array
   * - onEvent: function(eventName, dataObj) — called per event
   * returns Promise<void> that resolves when stream closes (event: done or [DONE])
   */
  async function parseSSEStream(reader, onEvent) {
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let currentEvent = 'message';
    let dataLines = [];

    const flushEvent = () => {
      if (dataLines.length === 0) return;
      const dataStr = dataLines.join('\n');
      dataLines = [];
      if (dataStr === '[DONE]') {
        onEvent('done', { done: true });
        currentEvent = 'message';
        return false; // stop
      }
      let parsed = dataStr;
      try { parsed = JSON.parse(dataStr); } catch { /* keep string */ }
      onEvent(currentEvent || 'message', parsed);
      currentEvent = 'message';
      return true;
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // split on \n\n (or \r\n\r\n)
      let idx;
      while ((idx = buffer.search(/\r?\n\r?\n/)) >= 0) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + (buffer.substr(idx, 4) === '\r\n\r\n' ? 4 : 2));

        const lines = chunk.split(/\r?\n/);
        for (const line of lines) {
          if (!line) continue;
          if (line.startsWith(':')) continue; // comment
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        const cont = flushEvent();
        if (cont === false) {
          try { await reader.cancel(); } catch {}
          return;
        }
      }
    }

    // tail
    if (buffer.trim()) {
      const lines = buffer.split(/\r?\n/);
      for (const line of lines) {
        if (!line) continue;
        if (line.startsWith('event:')) currentEvent = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
      }
      flushEvent();
    }
  }

  function streamPost(path, body, onEvent) {
    return new Promise(async (resolve, reject) => {
      let resp;
      try {
        resp = await fetch(BASE + path, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
          body: JSON.stringify(body),
        });
      } catch (e) {
        reject(new Error('网络异常：' + (e.message || e)));
        return;
      }

      if (!resp.ok || !resp.body) {
        let text = '';
        try { text = await resp.text(); } catch {}
        let payload = text;
        try { payload = JSON.parse(text); } catch {}
        const msg = (payload && (payload.detail || payload.error || payload.message)) || `HTTP ${resp.status}`;
        const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        err.status = resp.status;
        reject(err);
        return;
      }

      const reader = resp.body.getReader();
      try {
        await parseSSEStream(reader, onEvent);
        resolve();
      } catch (e) {
        reject(e);
      } finally {
        try { reader.releaseLock(); } catch {}
      }
    });
  }

  /* ----- public API ---------------------------------------------------- */
  const api = {
    BASE,

    async getSettings() {
      return jsonFetch(BASE + '/api/settings', { method: 'GET' });
    },

    // 读取完整配置（含明文 key），仅本机使用。优先用这个回填表单。
    async getSettingsRaw() {
      return jsonFetch(BASE + '/api/settings/raw', { method: 'GET' });
    },

    async saveSettings(cfg) {
      return jsonFetch(BASE + '/api/settings', { method: 'POST', body: cfg });
    },

    async testLlm({ base_url, api_key, model, prompt }) {
      return jsonFetch(BASE + '/api/settings/test/llm', {
        method: 'POST',
        body: { base_url, api_key, model, prompt: prompt || '用一句话介绍杭州西湖。' },
      });
    },

    async testAmap({ api_key }) {
      return jsonFetch(BASE + '/api/settings/test/amap', {
        method: 'POST',
        body: { api_key },
      });
    },

    streamTrip(req, onEvent) {
      return streamPost('/api/trip/plan/stream', req, onEvent);
    },

    streamChat(req, onEvent) {
      return streamPost('/api/chat/stream', req, onEvent);
    },

    // exposed for advanced usage
    _parseSSEStream: parseSSEStream,
  };

  global.api = api;
})(window);