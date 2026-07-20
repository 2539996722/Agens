/* ==========================================================================
   main.js — bootstrap: load settings, wire tabs, open modal
   ========================================================================== */
(function (global) {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const app = {
    config: null,
    mode: 'trip',

    switchMode(mode) {
      this.mode = mode;
      $$('.tab').forEach(t => {
        const active = t.dataset.mode === mode;
        t.classList.toggle('is-active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      $$('.mode-panel').forEach(p => {
        p.classList.toggle('is-active', p.id === `panel-${mode}`);
      });
    },

    openSettings() { Settings.open(); },
    saveConfig(cfg) { this.config = cfg; },

    onConfigSaved(cfg) {
      // could trigger UI updates here
    },
  };

  async function init() {
    // 加载已保存的配置（含明文 key，让设置页能直接回填之前填过的内容）。
    // raw 端点仅本机使用，不会有安全风险。
    try {
      const raw = await api.getSettingsRaw();
      if (raw && raw.ok && raw.config) {
        app.config = raw.config;
      } else {
        app.config = null;
      }
    } catch (e) {
      console.warn('[settings] raw load failed, fallback to public view:', e.message);
      // 兜底：试一下脱敏视图
      try {
        const pub = await api.getSettings();
        app.config = (pub && pub.config) || null;
      } catch (e2) {
        console.warn('[settings] public load failed:', e2.message);
        app.config = null;
      }
    }

    // tab switching
    $$('.tab').forEach(tab => {
      tab.addEventListener('click', () => app.switchMode(tab.dataset.mode));
    });

    // bind modules
    Settings.bind();
    Settings.setConfig(app.config);
    Trip.bind();
    Chat.bind();

    // quick keyboard shortcut: press "s" to open settings
    document.addEventListener('keydown', (e) => {
      if (e.key === 's' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const tag = (e.target && e.target.tagName) || '';
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        if (document.querySelector('#settings-modal.is-open')) return;
        e.preventDefault();
        app.openSettings();
      }
    });

    // settings may be required — auto-open if empty
    if (!app.config || !app.config.llm || !app.config.llm.api_key) {
      setTimeout(() => app.openSettings(), 400);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  global.app = app;
})(window);