/* ==========================================================================
   settings.js — settings modal: load / test / save
   ========================================================================== */
(function (global) {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  let isOpen = false;
  let currentConfig = null;

  function maskKey(k) {
    if (!k) return '';
    if (k.length <= 8) return '••••';
    return k.slice(0, 4) + '••••••' + k.slice(-4);
  }

  function fillForm(cfg) {
    const llm = (cfg && cfg.llm) || {};
    const amap = (cfg && cfg.amap) || {};
    // 直接回填完整 key（仅本地访问，无安全风险）。
    // 如果后端返回的是脱敏视图（带 _masked 后缀），fallback 到脱敏显示但不让用户误以为是新 key。
    const llmKey = llm.api_key != null ? llm.api_key : (llm.api_key_masked || '');
    const amapKey = amap.api_key != null ? amap.api_key : (amap.api_key_masked || '');

    $('#cfg-base-url').value = llm.base_url || '';
    $('#cfg-api-key').value = llmKey;
    $('#cfg-api-key').placeholder = llmKey ? '已保存（点击 👀 可显示/隐藏）' : 'sk-...';
    $('#cfg-model').value = llm.model || '';
    $('#cfg-reasoning-split').checked = !!llm.use_reasoning_split;
    $('#cfg-amap-key').value = amapKey;
    $('#cfg-amap-key').placeholder = amapKey ? '已保存（点击 👀 可显示/隐藏）' : 'a1b2c3d4...';
  }

  function readForm() {
    return {
      llm: {
        base_url: $('#cfg-base-url').value.trim(),
        api_key: $('#cfg-api-key').value.trim(),
        model: $('#cfg-model').value.trim(),
        reasoning_split: $('#cfg-reasoning-split').checked,
      },
      amap: {
        api_key: $('#cfg-amap-key').value.trim(),
      },
    };
  }

  function setTestResult(elId, ok, payload) {
    const el = $('#' + elId);
    if (!el) return;
    el.innerHTML = '';
    if (ok) {
      const latency = payload && payload.latency_ms != null ? `（${payload.latency_ms} ms）` : '';
      const sample = payload && (payload.sample_reply || payload.sample) ? ` · ${payload.sample_reply || payload.sample}` : '';
      el.innerHTML = `<span class="note note--ok" style="display:inline-block;margin:0;padding:4px 10px;">✅ 连接成功 ${latency}${escHtml(sample)}</span>`;
    } else {
      const err = (payload && (payload.error || payload.detail)) || '连接失败';
      el.innerHTML = `<span class="note note--err" style="display:inline-block;margin:0;padding:4px 10px;">❌ ${escHtml(String(err))}</span>`;
    }
  }

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  function open() {
    fillForm(currentConfig || (global.app && global.app.config) || {});
    // also clear old test results
    $('#test-llm-result').innerHTML = '';
    $('#test-amap-result').innerHTML = '';
    $('#settings-modal').classList.add('is-open');
    isOpen = true;
  }

  function close() {
    $('#settings-modal').classList.remove('is-open');
    isOpen = false;
  }

  function bind() {
    $('#open-settings-btn').addEventListener('click', open);
    $('#close-settings-btn').addEventListener('click', close);
    $('#cancel-settings-btn').addEventListener('click', close);
    $('#settings-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) close();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isOpen) close();
    });

    // password toggles
    $('#toggle-key-btn').addEventListener('click', () => {
      const i = $('#cfg-api-key');
      const btn = $('#toggle-key-btn');
      if (i.type === 'password') { i.type = 'text'; btn.textContent = '🙈'; }
      else { i.type = 'password'; btn.textContent = '👀'; }
    });
    $('#toggle-amap-btn').addEventListener('click', () => {
      const i = $('#cfg-amap-key');
      const btn = $('#toggle-amap-btn');
      if (i.type === 'password') { i.type = 'text'; btn.textContent = '🙈'; }
      else { i.type = 'password'; btn.textContent = '👀'; }
    });

    // test LLM
    $('#test-llm-btn').addEventListener('click', async () => {
      const btn = $('#test-llm-btn');
      const cfg = readForm();
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> 测试中…';
      try {
        const res = await api.testLlm({
          base_url: cfg.llm.base_url,
          api_key: cfg.llm.api_key,
          model: cfg.llm.model,
        });
        setTestResult('test-llm-result', !!res.ok, res);
      } catch (e) {
        setTestResult('test-llm-result', false, { error: e.message });
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span aria-hidden="true">🧪</span> 测试 LLM 连接';
      }
    });

    // test Amap
    $('#test-amap-btn').addEventListener('click', async () => {
      const btn = $('#test-amap-btn');
      const cfg = readForm();
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> 测试中…';
      try {
        const res = await api.testAmap({ api_key: cfg.amap.api_key });
        setTestResult('test-amap-result', !!res.ok, res);
      } catch (e) {
        setTestResult('test-amap-result', false, { error: e.message });
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span aria-hidden="true">🧪</span> 测试高德连接';
      }
    });

    // save
    $('#settings-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const cfg = readForm();
      // 用 currentConfig 作为"原始值"基线：如果用户没有改某个 key 字段，保留原值，
      // 避免意外覆盖。空字符串就当作"用户主动清空"处理。
      const base = (currentConfig && currentConfig.config) ? currentConfig.config : (currentConfig || {});
      const baseLlm = base.llm || {};
      const baseAmap = base.amap || {};
      cfg.llm.api_key = cfg.llm.api_key || baseLlm.api_key || '';
      cfg.amap.api_key = cfg.amap.api_key || baseAmap.api_key || '';

      if (!cfg.llm.base_url || !cfg.llm.api_key || !cfg.llm.model) {
        setTestResult('test-llm-result', false, { error: '请填写完整的 LLM 配置' });
        return;
      }
      if (!cfg.amap.api_key) {
        setTestResult('test-amap-result', false, { error: '请填写高德 Key' });
        return;
      }
      const btn = $('#save-settings-btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> 保存中…';
      try {
        const saved = await api.saveSettings(cfg);
        currentConfig = saved || cfg;
        if (global.app) {
          global.app.config = currentConfig;
          if (typeof global.app.onConfigSaved === 'function') global.app.onConfigSaved(currentConfig);
        }
        close();
      } catch (e) {
        setTestResult('test-llm-result', false, { error: e.message });
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span aria-hidden="true">💾</span> 保存配置';
      }
    });
  }

  global.Settings = {
    bind,
    open,
    close,
    setConfig(cfg) { currentConfig = cfg; fillForm(cfg); },
    getConfig() { return currentConfig; },
  };
})(window);