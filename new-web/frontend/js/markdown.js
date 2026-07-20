/* ==========================================================================
   markdown.js — tiny, safe markdown renderer (zero dependencies)
   Supports: headings, bold, italic, code, fenced code, lists, quotes,
             links, hr, inline html escape.
   ========================================================================== */
(function (global) {
  'use strict';

  const ESCAPE_MAP = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  function esc(s) {
    return String(s).replace(/[&<>"']/g, ch => ESCAPE_MAP[ch]);
  }

  function escapeAttr(s) { return esc(s); }

  // ---- inline transforms (applied to a text fragment) -----------------
  function applyInline(text) {
    let s = esc(text);

    // inline code first (so its content is not transformed)
    s = s.replace(/`([^`]+?)`/g, (_, c) => `<code>${c}</code>`);

    // images ![alt](url)
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g,
      (_, alt, url, title) => {
        const t = title ? ` title="${escapeAttr(title)}"` : '';
        return `<img alt="${escapeAttr(alt)}" src="${escapeAttr(url)}"${t} loading="lazy">`;
      });

    // links [text](url)
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g,
      (_, label, url, title) => {
        const t = title ? ` title="${escapeAttr(title)}"` : '';
        const safeUrl = /^(https?:|mailto:|tel:|#|\/)/i.test(url) ? url : '#';
        return `<a href="${escapeAttr(safeUrl)}"${t} target="_blank" rel="noopener">${label}</a>`;
      });

    // bold **text** or __text__
    s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__([^_]+?)__/g, '<strong>$1</strong>');

    // italic *text* or _text_  (avoid matching mid-word)
    s = s.replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,!?;:]|$)/g, '$1<em>$2</em>');
    s = s.replace(/(^|[\s(])_([^_\s][^_]*?)_(?=[\s).,!?;:]|$)/g, '$1<em>$2</em>');

    // strikethrough ~~text~~
    s = s.replace(/~~([^~]+?)~~/g, '<del>$1</del>');

    // hard line break (two trailing spaces)
    s = s.replace(/  \n/g, '<br>');

    return s;
  }

  // ---- block parser ----------------------------------------------------
  function render(src) {
    if (!src) return '';
    // normalize line endings
    let text = String(src).replace(/\r\n?/g, '\n');
    // collapse trailing spaces
    text = text.replace(/[ \t]+\n/g, '\n');

    const lines = text.split('\n');
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // fenced code block
      const fence = line.match(/^```(\w*)\s*$/);
      if (fence) {
        const lang = fence[1] || '';
        const code = [];
        i++;
        while (i < lines.length && !/^```\s*$/.test(lines[i])) {
          code.push(lines[i]);
          i++;
        }
        i++; // skip closing fence
        const cls = lang ? ` class="lang-${esc(lang)}"` : '';
        out.push(`<pre${cls}><code>${esc(code.join('\n'))}</code></pre>`);
        continue;
      }

      // heading ######
      const h = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
      if (h) {
        const level = h[1].length;
        const inner = applyInline(h[2]);
        const cls = ` class="sketch-underline"`;
        out.push(`<h${level}${cls}>${inner}</h${level}>`);
        i++;
        continue;
      }

      // horizontal rule
      if (/^\s*([-*_])\s*\1\s*\1[\s\1]*$/.test(line) || /^---+\s*$/.test(line)) {
        out.push('<hr>');
        i++;
        continue;
      }

      // blockquote (one or more consecutive lines starting with >)
      if (/^>\s?/.test(line)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          buf.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        out.push(`<blockquote>${applyInline(buf.join(' '))}</blockquote>`);
        continue;
      }

      // unordered list
      if (/^[\-\*\+]\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^[\-\*\+]\s+/.test(lines[i])) {
          const content = lines[i].replace(/^[\-\*\+]\s+/, '');
          items.push(applyInline(content));
          i++;
        }
        out.push(`<ul>${items.map(t => `<li>${t}</li>`).join('')}</ul>`);
        continue;
      }

      // ordered list
      if (/^\d+\.\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
          const content = lines[i].replace(/^\d+\.\s+/, '');
          items.push(applyInline(content));
          i++;
        }
        out.push(`<ol>${items.map(t => `<li>${t}</li>`).join('')}</ol>`);
        continue;
      }

      // blank line
      if (!line.trim()) {
        i++;
        continue;
      }

      // paragraph (collect consecutive non-blank, non-block-starting lines)
      const para = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^(#{1,6}\s|```|>\s?|[\-\*\+]\s|\d+\.\s|---+\s*$)/.test(lines[i])
      ) {
        para.push(lines[i]);
        i++;
      }
      out.push(`<p>${applyInline(para.join(' '))}</p>`);
    }

    return out.join('\n');
  }

  global.markdown = { render, esc };
})(window);