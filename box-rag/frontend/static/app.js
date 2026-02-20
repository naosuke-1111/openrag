/**
 * Box RAG Frontend — Single Page Application
 *
 * Communicates with the Box RAG backend API (same origin).
 */

'use strict';

const API = '';  // same-origin backend

// ── Utilities ────────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.error || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

function formatBytes(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function formatDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('ja-JP'); } catch { return iso; }
}

function el(id) { return document.getElementById(id); }

// ── Tab navigation ────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById('tab-' + tab).classList.remove('hidden');

    if (tab === 'documents') loadDocuments();
  });
});

// ── Tags ─────────────────────────────────────────────────────────────────────

const TAG_RE = /^[\u3000-\u9FFF\uF900-\uFAFF\uFF01-\uFF9F\u0041-\u005A\u0061-\u007A\u0030-\u0039\u3040-\u30FF\u4E00-\u9FFF\u00C0-\u024F]*$/;
const MAX_TAGS = 20;
const MAX_TAG_LEN = 64;
let tags = [];

function validateTag(raw) {
  const tag = raw.toLowerCase().trim();
  if (!tag) return null;
  if (tags.length >= MAX_TAGS) { showTagError(`最大 ${MAX_TAGS} タグまで`); return null; }
  if (tag.length > MAX_TAG_LEN) { showTagError(`タグは ${MAX_TAG_LEN} 文字以内`); return null; }
  if (!TAG_RE.test(tag)) { showTagError('半角記号・全角記号は使用できません'); return null; }
  if (tags.includes(tag)) { showTagError('重複タグです'); return null; }
  return tag;
}

function showTagError(msg) {
  el('tag-error').textContent = msg;
  el('tag-error').classList.remove('hidden');
  setTimeout(() => el('tag-error').classList.add('hidden'), 2500);
}

function renderTags() {
  const list = el('tag-list');
  list.innerHTML = tags.map(t =>
    `<span class="tag">${escHtml(t)}<span class="tag-remove" data-tag="${escHtml(t)}">✕</span></span>`
  ).join('');
  list.querySelectorAll('.tag-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      tags = tags.filter(t => t !== btn.dataset.tag);
      renderTags();
    });
  });
}

el('tag-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    const val = el('tag-input').value.trim().replace(/,$/, '');
    const tag = validateTag(val);
    if (tag) {
      tags.push(tag);
      renderTags();
      el('tag-input').value = '';
    }
  }
});

// ── Shared link resolution ────────────────────────────────────────────────────

let resolvedData = null;
let selectedFiles = new Set();  // Set of file IDs
let allFiles = [];               // flat list from backend

el('btn-resolve').addEventListener('click', async () => {
  const url = el('shared-link-url').value.trim();
  if (!url) { showError('resolve-error', 'URL を入力してください'); return; }

  el('resolve-error').classList.add('hidden');
  el('btn-resolve').disabled = true;
  el('btn-resolve').textContent = '解決中…';

  try {
    const body = {
      shared_link_url: url,
      shared_link_password: el('shared-link-password').value || null,
      tags,
    };
    const data = await apiFetch('/shared-link/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    resolvedData = data;
    allFiles = data.type === 'file' ? [data.item] : (data.files || []);
    selectedFiles.clear();

    showStep('step-selection');
    renderFileTree(data);
  } catch (err) {
    showError('resolve-error', err.message);
  } finally {
    el('btn-resolve').disabled = false;
    el('btn-resolve').textContent = 'リンクを解決';
  }
});

el('btn-back').addEventListener('click', () => showStep('step-link'));

el('btn-ingest').addEventListener('click', startIngestion);

function showStep(stepId) {
  document.querySelectorAll('.step').forEach(s => s.classList.add('hidden'));
  el(stepId).classList.remove('hidden');
}

function showError(elId, msg) {
  const e = el(elId);
  e.textContent = msg;
  e.classList.remove('hidden');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── File tree rendering ────────────────────────────────────────────────────────

function renderFileTree(data) {
  const title = el('selection-title');
  const treeEl = el('file-tree');

  if (data.type === 'file') {
    title.textContent = 'ファイル確認';
    const f = data.item;
    treeEl.innerHTML = `
      <div class="tree-item">
        <input type="checkbox" id="file-${f.id}" value="${f.id}" checked />
        <span class="item-icon">📄</span>
        <label for="file-${f.id}">${escHtml(f.name)}</label>
        <span class="item-meta">${formatBytes(f.size)} · ${formatDate(f.modified_at)}</span>
      </div>`;
    selectedFiles.add(f.id);
  } else {
    title.textContent = `フォルダ: ${escHtml(data.folder_name || '')}`;
    treeEl.innerHTML = renderTreeNode(data.tree, 0);
  }

  updateSelection();
  treeEl.querySelectorAll('input[type=checkbox][data-type=file]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) {
        if (selectedFiles.size >= 20) {
          cb.checked = false;
          alert('最大 20 ファイルまで選択できます');
          return;
        }
        selectedFiles.add(cb.value);
      } else {
        selectedFiles.delete(cb.value);
      }
      updateSelection();
    });
  });

  // Folder toggles
  treeEl.querySelectorAll('.folder-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const folderId = btn.dataset.folder;
      const childEl = el('folder-children-' + folderId);
      if (childEl) {
        const hidden = childEl.classList.toggle('hidden');
        btn.textContent = hidden ? '▶' : '▼';
      }
    });
  });
}

function renderTreeNode(node, depth) {
  if (node.type === 'file') {
    return `
      <div class="tree-item indent-${Math.min(depth, 3)}">
        <input type="checkbox" id="file-${node.id}" value="${node.id}" data-type="file" />
        <span class="item-icon">📄</span>
        <label for="file-${node.id}">${escHtml(node.name)}</label>
        <span class="item-meta">${formatBytes(node.size)} · ${formatDate(node.modified_at)}</span>
      </div>`;
  }

  // Folder
  const children = (node.children || []).map(c => renderTreeNode(c, depth + 1)).join('');
  const fileCount = node.file_count || 0;
  return `
    <div class="tree-item folder indent-${Math.min(depth, 3)}">
      <button class="folder-toggle btn-ghost btn-sm" data-folder="${node.id}">▼</button>
      <span class="item-icon">📁</span>
      <span>${escHtml(node.name)}</span>
      <span class="item-meta">${fileCount} ファイル</span>
    </div>
    <div id="folder-children-${node.id}">${children}</div>`;
}

function updateSelection() {
  el('selection-count').textContent = `${selectedFiles.size} / 20 選択`;
  el('btn-ingest').disabled = selectedFiles.size === 0;
}

// ── Ingestion ─────────────────────────────────────────────────────────────────

let currentJobId = null;
let pollTimer = null;

async function startIngestion() {
  if (selectedFiles.size === 0) return;

  const filesToIngest = allFiles.filter(f => selectedFiles.has(f.id));

  showStep('step-progress');
  el('progress-bar').style.width = '0%';
  el('progress-label').textContent = `0 / ${filesToIngest.length}`;
  el('btn-done').classList.add('hidden');
  el('progress-errors').classList.add('hidden');

  try {
    const body = {
      shared_link_url: el('shared-link-url').value.trim(),
      shared_link_password: el('shared-link-password').value || null,
      tags,
      files: filesToIngest,
      force_reingest: false,
    };

    const result = await apiFetch('/ingest/selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    currentJobId = result.job_id;
    pollProgress(result.total);
  } catch (err) {
    showStep('step-link');
    showError('resolve-error', '取り込み開始に失敗しました: ' + err.message);
  }
}

function pollProgress(total) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try {
      const job = await apiFetch('/ingest/jobs/' + currentJobId);
      const done = job.done + job.failed;
      const pct = total > 0 ? Math.round(done / total * 100) : 0;

      el('progress-bar').style.width = pct + '%';
      el('progress-label').textContent = `${done} / ${total}`;

      if (job.errors && job.errors.length > 0) {
        el('progress-errors').classList.remove('hidden');
        el('progress-errors').innerHTML =
          '<strong>エラー</strong><ul>' +
          job.errors.map(e => `<li>${escHtml(e.file)}: ${escHtml(e.error)}</li>`).join('') +
          '</ul>';
      }

      if (job.status === 'running') {
        pollProgress(total);
      } else {
        el('btn-done').classList.remove('hidden');
      }
    } catch (err) {
      console.error('Poll error:', err);
      pollProgress(total);
    }
  }, 1500);
}

el('btn-done').addEventListener('click', () => {
  tags = [];
  renderTags();
  el('shared-link-url').value = '';
  el('shared-link-password').value = '';
  selectedFiles.clear();
  resolvedData = null;
  allFiles = [];
  showStep('step-link');
});

// ── Documents tab ─────────────────────────────────────────────────────────────

el('btn-refresh-docs').addEventListener('click', loadDocuments);
el('doc-filter-status').addEventListener('change', loadDocuments);

async function loadDocuments() {
  const tagsFilter = el('doc-filter-tags').value.trim();
  const statusFilter = el('doc-filter-status').value;
  let url = '/documents?size=100';
  if (tagsFilter) url += '&tags=' + encodeURIComponent(tagsFilter);
  if (statusFilter) url += '&status=' + encodeURIComponent(statusFilter);

  el('doc-list').innerHTML = '<p class="muted">読み込み中…</p>';
  try {
    const data = await apiFetch(url);
    renderDocuments(data.documents, data.total);
  } catch (err) {
    el('doc-list').innerHTML = `<p class="field-error">エラー: ${escHtml(err.message)}</p>`;
  }
}

function renderDocuments(docs, total) {
  if (!docs.length) {
    el('doc-list').innerHTML = '<p class="muted">ドキュメントがありません</p>';
    return;
  }
  el('doc-list').innerHTML = docs.map(doc => {
    const statusCls = 'status-' + (doc.status || 'pending');
    const tagsHtml = (doc.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join('');
    return `
      <div class="doc-card" id="doc-card-${doc.document_id}">
        <div class="doc-info">
          <div class="doc-name">📄 ${escHtml(doc.file_name)}</div>
          <div class="doc-tags tag-list">${tagsHtml}</div>
          <div class="doc-meta">
            chunks: ${doc.chunk_count || 0} ·
            updated: ${formatDate(doc.updated_at)} ·
            ${formatBytes(doc.file_size)}
          </div>
          ${doc.error ? `<div class="field-error">エラー: ${escHtml(doc.error)}</div>` : ''}
        </div>
        <div style="display:flex;flex-direction:column;gap:.5rem;align-items:flex-end">
          <span class="status-badge ${statusCls}">${escHtml(doc.status)}</span>
          <button class="btn btn-danger btn-sm" onclick="deleteDocument('${doc.document_id}')">削除</button>
        </div>
      </div>`;
  }).join('');
}

async function deleteDocument(documentId) {
  if (!confirm('このドキュメントとチャンクを削除しますか？')) return;
  try {
    await apiFetch('/documents/' + documentId, { method: 'DELETE' });
    const card = el('doc-card-' + documentId);
    if (card) card.remove();
  } catch (err) {
    alert('削除に失敗しました: ' + err.message);
  }
}

// ── Search tab ────────────────────────────────────────────────────────────────

el('btn-search').addEventListener('click', runSearch);
el('search-query').addEventListener('keydown', e => {
  if (e.key === 'Enter') runSearch();
});

async function runSearch() {
  const query = el('search-query').value.trim();
  if (!query) { showError('search-error', '検索クエリを入力してください'); return; }

  el('search-error').classList.add('hidden');
  el('search-results').classList.add('hidden');
  el('btn-search').disabled = true;
  el('btn-search').textContent = '検索中…';

  const tagsRaw = el('search-tags').value.trim();
  const searchTags = tagsRaw ? tagsRaw.split(/[,\s]+/).filter(Boolean) : [];
  const generate = el('search-generate').checked;

  try {
    const result = await apiFetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, tags: searchTags.length ? searchTags : null, generate_answer: generate }),
    });
    renderSearchResults(result);
  } catch (err) {
    showError('search-error', err.message);
  } finally {
    el('btn-search').disabled = false;
    el('btn-search').textContent = '検索';
  }
}

function renderSearchResults(data) {
  const resultsEl = el('search-results');
  resultsEl.classList.remove('hidden');

  // Answer
  const answerBox = el('answer-box');
  if (data.answer) {
    answerBox.classList.remove('hidden');
    el('answer-text').textContent = data.answer;
  } else {
    answerBox.classList.add('hidden');
  }

  // Chunks
  const chunksEl = el('chunks-list');
  if (!data.chunks.length) {
    chunksEl.innerHTML = '<p class="muted">関連するチャンクが見つかりませんでした</p>';
    return;
  }
  chunksEl.innerHTML = data.chunks.map((c, i) => {
    const tags = (c.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join('');
    return `
      <div class="chunk-card">
        <div class="chunk-meta">
          [${i + 1}] 📄 ${escHtml(c.file_name)}
          ${tags ? ` &nbsp; ${tags}` : ''}
          · chunk #${c.chunk_index ?? '?'}
          · score: ${c.score?.toFixed(4) ?? '—'}
        </div>
        <pre class="chunk-text">${escHtml(c.text)}</pre>
      </div>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────────────

showStep('step-link');
