const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = null;
let selectedTaskId = null;
let previewUrl = null;
let toastTimer;

function toast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('show'), 3500);
}
function errorMessage(data) {
  return typeof data?.detail === 'string' ? data.detail : 'Notika kļūda. Mēģini vēlreiz.';
}
async function request(url, options = {}) {
  const response = await fetch(url, {credentials:'same-origin', cache:'no-store', ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorMessage(data));
  return data;
}
function fmtDate(value) {
  if (!value) return '';
  const date = new Date(value.replace(' ', 'T')+'Z');
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleString('lv-LV',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
}
function statusName(status) {
  return ({pending:'Gaida apstiprinājumu',approved:'Apstiprināts ✓',rejected:'Noraidīts, iesniedz vēlreiz'})[status] || status;
}
function render() {
  if (!state) return;
  const team = state.team;
  document.body.classList.toggle('playing', Boolean(team));
  $('hero').classList.toggle('hidden', Boolean(team));
  $('joinPanel').classList.toggle('hidden', Boolean(team));
  $('teamPanel').classList.toggle('hidden', !team);
  if (team) {
    const result = state.leaderboard.find(r => r.id === team.id) || {points:0,done:0};
    $('currentTeamName').textContent = team.name;
    $('teamScore').textContent = result.points;
    $('teamDone').textContent = `${result.done}/${state.tasks.length}`;
    const pending = state.tasks.filter(t => t.submission?.status==='pending').length;
    $('teamProgress').textContent = `Tavā kontā ir ${result.done} apstiprināti un ${pending} vērtēšanā esoši uzdevumi.`;
  }
  $('tasksCount').textContent = `${state.tasks.length} UZDEVUMI`;
  $('taskGrid').innerHTML = state.tasks.map((task, idx) => {
    const sub = task.submission;
    const status = sub?.status;
    const button = !team ? 'Pievienojies, lai iesniegtu' : status === 'pending' ? '⏳ Gaida vērtējumu' : status === 'approved' ? '✓ Izpildīts' : status === 'rejected' ? '↻ Iesniegt vēlreiz' : 'Uzņemt foto ↗';
    const klass = status || '';
    const disabled = !team || status === 'pending' || status === 'approved';
    return `<article class="mission-card">
      <div class="mission-art art-${idx%8}"><span class="mission-number">#${String(idx+1).padStart(2,'0')}</span><span class="big-emoji" aria-hidden="true">${escapeHTML(task.emoji)}</span></div>
      <div class="mission-card-body"><div class="mission-topline"><span class="cat-label">${escapeHTML(task.category)}</span><span class="points-label">+${task.points} P</span></div>
      <h3>${escapeHTML(task.title)}</h3><p>${escapeHTML(task.description)}</p>
      ${task.has_reference ? `<a class="reference-link" href="/api/reference/${task.id}" target="_blank" rel="noopener">👀 Skatīt parauga pozu ↗</a>` : ''}
      ${status==='rejected' && sub?.note ? `<span class="small-note">Piezīme: ${escapeHTML(sub.note)}</span>` : ''}
      <button class="mission-action ${klass}" type="button" data-task="${task.id}" ${disabled?'disabled':''}>${button} <span aria-hidden="true">${disabled?'':'→'}</span></button>
      ${sub?.photo_url ? `<a class="reference-link" href="${sub.photo_url}" target="_blank" rel="noopener">Mans iesniegtais foto ↗</a>` : ''}
      </div></article>`;
  }).join('') || '<div class="loading-card">Pagaidām uzdevumu nav.</div>';
  $('leaderboard').innerHTML = state.leaderboard.map(entry => `
    <div class="leader-row ${team && entry.id===team.id?'me':''}">
      <div class="rank-num ${entry.rank<=3?'top':''}">${entry.rank<=3?['🥇','🥈','🥉'][entry.rank-1]:`#${entry.rank}`}</div>
      <div class="leader-name">${escapeHTML(entry.name)} ${team && entry.id===team.id?'(tu)':''}<span class="leader-sub">Komanda #${String(entry.id).padStart(2,'0')}</span></div>
      <div class="leader-tasks">${entry.done} uzd.</div><div class="leader-points">${entry.points} <small>p.</small></div>
    </div>`).join('') || '<div class="loading-card">Vēl nav komandu.</div>';
}
async function refresh() {
  try { state = await request('/api/state'); render(); }
  catch(err) { if (!state) $('taskGrid').textContent = err.message; }
}
$('joinForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('joinMessage').textContent = '';
  const button = e.currentTarget.querySelector('button'); button.disabled = true;
  try {
    await request('/api/team/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('teamCode').value.trim().toUpperCase()})});
    await refresh(); toast('Tu esi komandā! Lai sākas foto medības. 📸');
  } catch(err) { $('joinMessage').textContent = err.message; }
  finally { button.disabled = false; }
});
$('logoutBtn').addEventListener('click', async () => { await request('/api/team/logout',{method:'POST'}); await refresh(); toast('Tu izgāji no komandas.'); });
$('taskGrid').addEventListener('click', event => {
  const button = event.target.closest('button[data-task]');
  if (!button || button.disabled) return;
  const task = state?.tasks.find(t => t.id === Number(button.dataset.task));
  if (!task || !state.team) return;
  selectedTaskId = task.id;
  $('dialogEmoji').textContent = task.emoji;
  $('dialogTitle').textContent = task.title;
  $('dialogDescription').textContent = task.description;
  $('dialogReference').classList.toggle('hidden', !task.has_reference);
  if (task.has_reference) $('dialogReference').src = `/api/reference/${task.id}`;
  $('fileLabel').textContent = 'Izvēlies fotoattēlu';
  $('photoInput').value = '';
  $('photoPreview').classList.add('hidden');
  $('uploadMessage').textContent = '';
  $('uploadDialog').showModal();
});
$('photoInput').addEventListener('change', () => {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  const file = $('photoInput').files?.[0];
  if (file) {
    previewUrl = URL.createObjectURL(file);
    $('photoPreview').src = previewUrl;
    $('photoPreview').classList.remove('hidden');
    $('fileLabel').textContent = file.name;
  }
});
async function optimizePhoto(file) {
  if (file.size < 2.5 * 1024 * 1024) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1800 / Math.max(bitmap.width,bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1,Math.round(bitmap.width*scale));
    canvas.height = Math.max(1,Math.round(bitmap.height*scale));
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    bitmap.close?.();
    const blob = await new Promise(res => canvas.toBlob(res,'image/jpeg',.82));
    if (blob) return new File([blob],'foto.jpg',{type:'image/jpeg'});
  } catch(e) { /* Server will validate original file */ }
  return file;
}
$('uploadForm').addEventListener('submit', async e => {
  e.preventDefault();
  const file = $('photoInput').files?.[0];
  if (!file || !selectedTaskId) return;
  $('uploadMessage').textContent = '';
  const button = $('uploadSubmit'); button.disabled = true; button.textContent = 'Iesūta foto…';
  try {
    const form = new FormData();form.append('file',await optimizePhoto(file));
    await request(`/api/team/upload/${selectedTaskId}`,{method:'POST',body:form});
    $('uploadDialog').close();
    await refresh();toast('Foto iesūtīts! Tagad jāgaida apstiprinājums. ✨');
  } catch(err) { $('uploadMessage').textContent = err.message; }
  finally { button.disabled = false;button.innerHTML = 'Iesniegt vērtēšanai <span>→</span>'; }
});
setInterval(refresh,15000);
refresh();
