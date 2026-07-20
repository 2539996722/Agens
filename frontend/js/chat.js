/* ==========================================================================
   chat.js — daily chat mode with tool-call cards
   ========================================================================== */
(function (global) {
  'use strict';

  const $ = (s) => document.querySelector(s);

  let messages = []; // [{role, content}]
  let busy = false;

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  function bind() {
    $('#chat-form').addEventListener('submit', onSubmit);
    $('#chat-clear-btn').addEventListener('click', clearChat);
    pushGreeting();

    // Enter to send, Shift+Enter for newline
    $('#chat-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        $('#chat-form').requestSubmit();
      }
    });
  }

  function pushGreeting() {
    if ($('#chat-window').children.length > 0) return;
    pushAssistantGreeting();
  }

  function clearChat() {
    messages = [];
    $('#chat-window').innerHTML = '';
    pushAssistantGreeting();
  }

  function pushAssistantGreeting() {
    const div = document.createElement('div');
    div.className = 'msg msg--assistant';
    div.innerHTML = `
      <div class="msg__bubble">你好呀，我是你的旅行小助手 ✏️<br>想去哪里？或者直接问我附近的美食～</div>
      <div class="msg__meta">AI · ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    $('#chat-window').appendChild(div);
    scrollToBottom();
  }

  function scrollToBottom() {
    const win = $('#chat-window');
    win.scrollTop = win.scrollHeight;
  }

  function renderUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'msg msg--user';
    div.innerHTML = `
      <div class="msg__bubble">${escHtml(text)}</div>
      <div class="msg__meta">我 · ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    $('#chat-window').appendChild(div);
    scrollToBottom();
  }

  function createAssistantBubble() {
    const div = document.createElement('div');
    div.className = 'msg msg--assistant';
    div.innerHTML = `
      <div class="msg__bubble empty"><span class="loader"><span class="dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span></span></div>
      <div class="msg__meta">AI · ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    $('#chat-window').appendChild(div);
    scrollToBottom();
    return div.querySelector('.msg__bubble');
  }

  function createToolCard(name, args, status) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    const argsStr = (() => {
      try { return JSON.stringify(args || {}, null, 2); } catch { return '{}'; }
    })();
    card.innerHTML = `
      <div class="tool-card__title">
        <span>🔧</span>
        <span>高德 · ${escHtml(name || 'tool')}</span>
        <span class="badge badge--info">${escHtml(status || '调用中…')}</span>
      </div>
      <div class="tool-card__body">
        <div>📥 参数：</div>
        <pre>${escHtml(argsStr)}</pre>
        <div class="tool-result" hidden></div>
      </div>
    `;
    $('#chat-window').appendChild(card);
    scrollToBottom();
    return card;
  }

  function appendToolResult(card, result) {
    const slot = card.querySelector('.tool-result');
    slot.hidden = false;
    const status = card.querySelector('.badge');
    if (status) { status.textContent = '✅ 已返回'; status.classList.remove('badge--info'); status.classList.add('badge--ok'); }
    const resultStr = (() => {
      if (typeof result === 'string') return result;
      try { return JSON.stringify(result, null, 2); } catch { return String(result); }
    })();
    slot.innerHTML = `<div style="margin-top:8px;">📤 结果：</div><pre>${escHtml(resultStr)}</pre>`;
    scrollToBottom();
  }

  function setAssistantBubbleText(bubble, text) {
    bubble.classList.remove('empty');
    bubble.innerHTML = markdown.render(text);
    scrollToBottom();
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (busy) return;

    const input = $('#chat-input');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    renderUserMessage(text);
    messages.push({ role: 'user', content: text });

    const toolsEnabled = $('#tools-enabled').checked;
    await runAssistantTurn(toolsEnabled);
  }

  async function runAssistantTurn(toolsEnabled) {
    busy = true;
    setBusy(true);

    const bubble = createAssistantBubble();
    let assistantText = '';
    const openToolCards = new Map(); // id -> card

    try {
      await api.streamChat(
        { messages: messages.map(m => ({ role: m.role, content: m.content })), tools_enabled: !!toolsEnabled },
        (event, data) => {
          if (event === 'tool_call') {
            const id = (data && (data.id || data.tool_id)) || ('tc_' + Math.random().toString(36).slice(2, 8));
            const name = (data && (data.name || data.tool || data.function)) || 'tool';
            const args = (data && (data.args || data.arguments || data.input)) || {};
            const card = createToolCard(name, args, '调用中…');
            openToolCards.set(id, { card, name });
          } else if (event === 'tool_result') {
            const id = (data && (data.id || data.tool_id)) || null;
            const result = (data && (data.result || data.output || data)) ;
            let target = id && openToolCards.get(id);
            if (!target) {
              // fallback: most recent
              const last = Array.from(openToolCards.values()).pop();
              if (last) target = last;
            }
            if (target) appendToolResult(target.card, result);
          } else if (event === 'delta') {
            const txt = (data && (data.text || data.delta || data.content)) || '';
            if (txt) {
              assistantText += txt;
              setAssistantBubbleText(bubble, assistantText);
            }
          } else if (event === 'content') {
            const txt = (data && (data.text || data.delta || data.content)) || '';
            if (txt) {
              assistantText += txt;
              setAssistantBubbleText(bubble, assistantText);
            }
          } else if (event === 'error') {
            showError(bubble, (data && (data.message || data.error)) || '请求失败');
          } else if (event === 'done') {
            // finalize
            if (!assistantText) setAssistantBubbleText(bubble, '（无回复内容）');
          }
        }
      );
    } catch (e) {
      showError(bubble, e.message || String(e));
    } finally {
      if (assistantText) messages.push({ role: 'assistant', content: assistantText });
      setBusy(false);
      busy = false;
    }
  }

  function showError(bubble, msg) {
    bubble.classList.remove('empty');
    bubble.innerHTML = `<span style="color:#b84545;">❌ ${escHtml(msg)}</span>`;
    scrollToBottom();
  }

  function setBusy(b) {
    $('#chat-send-btn').disabled = b;
    $('#chat-cancel-btn').hidden = !b;
    $('#chat-send-btn').innerHTML = b
      ? '<span class="spinner"></span>'
      : '<span aria-hidden="true">📨</span> 发送';
    $('#chat-input').disabled = b;
  }

  global.Chat = { bind };
})(window);