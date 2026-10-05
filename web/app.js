/* 史莱姆任务管理 · 前端逻辑（原生 JS） */
const state = {
  scope: 'today',
  tasks: [],
  editingId: null,
  color: '#5ed49a',
};

const $ = sel => document.querySelector(sel);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

/* ---------------- 时间工具 ---------------- */
const pad = n => String(n).padStart(2, '0');

function fmtParts(iso) {
  const d = new Date(iso);
  return {
    d,
    date: `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    hm: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

function fmtRange(startIso, endIso) {
  const s = fmtParts(startIso), e = fmtParts(endIso);
  if (s.date === e.date) {
    return `${s.date} ${s.hm} ~ ${e.hm}`;
  }
  return `${s.date} ${s.hm} → ${e.date} ${e.hm}`;
}

function humanize(task) {
  const now = new Date();
  const start = new Date(task.start);
  const end = new Date(task.end_time);
  const mins = ms => Math.round(ms / 60000);

  if (task.status === 'completed') return '';
  if (task.status === 'expired') return '已超过结束时间';
  if (task.status === 'pending') {
    const m = mins(start - now);
    if (m <= 0) return '即将开始';
    if (m < 60) return `${m} 分钟后开始`;
    if (m < 60 * 24) return `${Math.floor(m / 60)} 小时 ${m % 60} 分后开始`;
    return `${Math.floor(m / 1440)} 天后开始`;
  }
  // in_progress
  const m = mins(end - now);
  if (m <= 0) return '即将结束';
  if (m < 60) return `剩余 ${m} 分钟`;
  return `剩余 ${Math.floor(m / 60)} 小时 ${m % 60} 分`;
}

/* ---------------- 渲染 ---------------- */
async function loadTasks() {
  const qs = new URLSearchParams({
    scope: state.scope,
    include_completed: 'true',
  });
  state.tasks = await api(`/api/tasks?${qs}`);
  render();
}

function render() {
  const list = $('#task-list');
  const empty = $('#empty-state');
  list.innerHTML = '';

  if (state.tasks.length === 0) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  for (const t of state.tasks) {
    const card = document.createElement('div');
    card.className = `task-card ${t.status === 'completed' ? 'is-done' : ''}`;

    const bar = document.createElement('div');
    bar.className = 'task-bar';
    bar.style.background = t.color;

    const main = document.createElement('div');
    main.className = 'task-main';

    const title = document.createElement('div');
    title.className = 'task-title';
    title.textContent = t.title;

    const meta = document.createElement('div');
    meta.className = 'task-meta';
    const time = document.createElement('span');
    time.textContent = '🕑 ' + fmtRange(t.start_time, t.end_time);
    meta.appendChild(time);
    const hint = humanize(t);
    if (hint) {
      const h = document.createElement('span');
      h.textContent = hint;
      meta.appendChild(h);
    }

    main.appendChild(title);
    main.appendChild(meta);
    if (t.note) {
      const note = document.createElement('div');
      note.className = 'task-note';
      note.textContent = t.note;
      main.appendChild(note);
    }

    const side = document.createElement('div');
    side.className = 'task-side';
    const badge = document.createElement('span');
    badge.className = `badge ${t.status}`;
    badge.textContent = t.status_label;
    side.appendChild(badge);

    const actions = document.createElement('div');
    actions.className = 'card-actions';
    if (t.status !== 'completed') {
      const done = document.createElement('button');
      done.className = 'mini-btn done';
      done.textContent = '完成';
      done.onclick = () => completeTask(t.id);
      actions.appendChild(done);
    }
    const edit = document.createElement('button');
    edit.className = 'mini-btn';
    edit.textContent = '编辑';
    edit.onclick = () => openModal(t);
    const del = document.createElement('button');
    del.className = 'mini-btn del';
    del.textContent = '删除';
    del.onclick = () => removeTask(t.id);
    side.appendChild(actions);

    card.append(bar, main, side);
    list.appendChild(card);
  }
}

/* ---------------- 操作 ---------------- */
async function completeTask(id) {
  await api(`/api/tasks/${id}/complete`, { method: 'POST' });
  loadTasks();
}

async function removeTask(id) {
  if (!confirm('确定删除这个任务吗？')) return;
  await api(`/api/tasks/${id}`, { method: 'DELETE' });
  loadTasks();
}

/* ---------------- 弹窗 ---------------- */
function localInputValue(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function openModal(task) {
  $('#form-error').hidden = true;
  if (task) {
    state.editingId = task.id;
    $('#modal-title').textContent = '编辑任务';
    $('#f-title').value = task.title;
    $('#f-start').value = task.start_time.slice(0, 16);
    $('#f-end').value = task.end_time.slice(0, 16);
    $('#f-remind').value = task.remind_before;
    $('#f-note').value = task.note || '';
    state.color = task.color;
  } else {
    state.editingId = null;
    $('#modal-title').textContent = '新建任务';
    const now = new Date();
    const start = new Date(now);
    start.setHours(now.getMinutes() > 0 ? now.getHours() + 1 : now.getHours(), 0, 0, 0);
    const end = new Date(start.getTime() + 3600000);
    $('#f-title').value = '';
    $('#f-start').value = localInputValue(start);
    $('#f-end').value = localInputValue(end);
    $('#f-remind').value = '5';
    $('#f-note').value = '';
    state.color = '#5ed49a';
  }
  document.querySelectorAll('.color-dot').forEach(dot => {
    dot.classList.toggle('selected', dot.dataset.color === state.color);
  });
  $('#modal').hidden = false;
  $('#f-title').focus();
}

function closeModal() {
  $('#modal').hidden = true;
  state.editingId = null;
}

async function submitForm(e) {
  e.preventDefault();
  const payload = {
    title: $('#f-title').value,
    start_time: $('#f-start').value,
    end_time: $('#f-end').value,
    remind_before: Number($('#f-remind').value),
    color: state.color,
    note: $('#f-note').value,
  };
  const errEl = $('#form-error');
  try {
    if (state.editingId) {
      await api(`/api/tasks/${state.editingId}`, {
        method: 'PUT', body: JSON.stringify(payload),
      });
    } else {
      await api('/api/tasks', {
        method: 'POST', body: JSON.stringify(payload),
      });
    }
    closeModal();
    loadTasks();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.hidden = false;
  }
}

/* ---------------- 事件绑定 ---------------- */
document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.scope = tab.dataset.scope;
    loadTasks();
  };
});

document.querySelectorAll('.color-dot').forEach(dot => {
  dot.onclick = () => {
    state.color = dot.dataset.color;
    document.querySelectorAll('.color-dot').forEach(d =>
      d.classList.toggle('selected', d === dot));
  };
});

$('#btn-new').onclick = () => openModal(null);
$('#modal-close').onclick = closeModal;
$('#modal-cancel').onclick = closeModal;
$('#task-form').onsubmit = submitForm;
$('#modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});

loadTasks();
setInterval(() => { if ($('#modal').hidden) loadTasks(); }, 15000);
