/* ==========================================================================
   trip.js — trip planning mode (form + streaming render)
   ========================================================================== */
(function (global) {
  'use strict';

  const $ = (s) => document.querySelector(s);

  let selectedInterests = new Set();
  let abortController = null;
  let finalContent = '';

  function bind() {
    // interest chips
    document.querySelectorAll('#trip-interests .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const v = chip.getAttribute('data-value');
        if (selectedInterests.has(v)) {
          selectedInterests.delete(v);
          chip.classList.remove('is-active');
        } else {
          selectedInterests.add(v);
          chip.classList.add('is-active');
        }
      });
    });

    $('#trip-form').addEventListener('submit', onSubmit);
    $('#trip-cancel-btn').addEventListener('click', cancel);
    $('#download-md-btn').addEventListener('click', downloadMd);
    $('#copy-md-btn').addEventListener('click', copyMd);
  }

  function reset() {
    finalContent = '';
    $('#plan-area').hidden = false;
    $('#reasoning-pre').textContent = '';
    $('#plan-content-pre').textContent = '';
    $('#plan-content').innerHTML = '';
    $('#plan-content').hidden = true;
    $('#streaming-status').hidden = false;
    $('#refs-list').innerHTML = '<p style="color:var(--ink-muted);font-family:var(--font-subtitle);">还没出现引用～</p>';
    $('#plan-error').hidden = true;
    $('#plan-error').textContent = '';
    $('#download-md-btn').hidden = true;
    $('#copy-md-btn').hidden = true;
    $('#reasoning-box').open = false;
    document.querySelector('#plan-area').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function setBusy(busy) {
    $('#trip-submit-btn').disabled = busy;
    $('#trip-cancel-btn').hidden = !busy;
    $('#trip-submit-btn').innerHTML = busy
      ? '<span class="spinner"></span> 生成中…'
      : '<span aria-hidden="true">✨</span> 生成计划';
  }

  function cancel() {
    if (abortController) {
      try { abortController.abort(); } catch {}
      abortController = null;
    }
    setBusy(false);
    $('#streaming-status').innerHTML = '<span aria-hidden="true">⏹️</span> 已取消';
  }

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  async function onSubmit(e) {
    e.preventDefault();

    const req = {
      origin: $('#trip-origin').value.trim(),
      destination: $('#trip-destination').value.trim(),
      days: parseInt($('#trip-days').value, 10) || 1,
      travelers: parseInt($('#trip-people').value, 10) || 1,
      interests: Array.from(selectedInterests),
      extra: $('#trip-extra').value.trim(),
    };

    if (!req.origin || !req.destination) return;

    reset();
    setBusy(true);

    try {
      await api.streamTrip(req, (event, data) => onEvent(event, data));
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      setBusy(false);
      abortController = null;
    }
  }

  function onEvent(event, data) {
    if (event === 'reasoning') {
      const txt = (data && (data.text || data.delta || data.content)) || '';
      if (txt) {
        $('#reasoning-pre').textContent += txt;
        $('#reasoning-box').open = true;
      }
    } else if (event === 'content') {
      const txt = (data && (data.text || data.delta || data.content)) || '';
      if (txt) {
        finalContent += txt;
        $('#plan-content-pre').textContent = finalContent;
        // live markdown preview
        try {
          $('#plan-content').innerHTML = markdown.render(finalContent);
          $('#plan-content').hidden = false;
        } catch { /* ignore partial parse errors */ }
      }
    } else if (event === 'refs') {
      const refs = extractRefs(data);
      if (refs && refs.length) renderRefs(refs);
    } else if (event === 'error') {
      showError((data && (data.message || data.error)) || '生成出错啦');
    } else if (event === 'done') {
      // finalize
      try {
        $('#plan-content').innerHTML = markdown.render(finalContent);
        $('#plan-content').hidden = false;
      } catch (e) {
        showError('Markdown 渲染失败：' + e.message);
      }
      $('#plan-content-pre').textContent = finalContent;
      $('#streaming-status').hidden = true;
      if (finalContent) {
        $('#download-md-btn').hidden = false;
        $('#copy-md-btn').hidden = false;
      }
    }
  }

  function extractRefs(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.refs)) return data.refs;
    if (Array.isArray(data.pois)) return data.pois;
    if (Array.isArray(data.places)) return data.places;
    if (Array.isArray(data.results)) return data.results;
    return [];
  }

  function renderRefs(refs) {
    const wrap = $('#refs-list');
    wrap.innerHTML = '';
    refs.forEach((r, idx) => {
      const name = r.name || r.title || r.address || `地点 ${idx + 1}`;
      const addr = r.address || r.location || r.district || '';
      const type = r.type || r.category || '';
      const tag = r.tag || r.id || `#${idx + 1}`;
      const card = document.createElement('div');
      card.className = 'ref-card';
      card.innerHTML = `
        <span class="ref-tag">${escHtml(tag)}</span>
        <h4>${escHtml(name)}</h4>
        <div class="ref-meta">${escHtml(addr)}</div>
        ${type ? `<div style="margin-top:6px;"><span class="tag">${escHtml(type)}</span></div>` : ''}
      `;
      wrap.appendChild(card);
    });
  }

  function showError(msg) {
    const el = $('#plan-error');
    el.hidden = false;
    el.textContent = '❌ ' + msg;
    $('#streaming-status').hidden = true;
  }

  function downloadMd() {
    if (!finalContent) return;
    const blob = new Blob([finalContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trip-plan-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }

  async function copyMd() {
    if (!finalContent) return;
    try {
      await navigator.clipboard.writeText(finalContent);
      const btn = $('#copy-md-btn');
      const old = btn.innerHTML;
      btn.innerHTML = '<span aria-hidden="true">✅</span> 已复制';
      setTimeout(() => { btn.innerHTML = old; }, 1500);
    } catch (e) {
      alert('复制失败：' + e.message);
    }
  }

  global.Trip = { bind };
})(window);