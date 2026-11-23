const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data = null;
let editTaskId = null;
let toastTimer;
function toast(message) { $('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3500); }
async function api(url, options={}) {
  const response = await fetch(url,{credentials:'same-origin',cache:'no-store',...options});
  const obj = await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(typeof obj.detail==='string'?obj.detail:'Radās kļūda.');
  return obj;
}
function json(method, value) { return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(value)}; }
function fmtDate(value) {if (!value) return '';const d=new Date(value.replace(' ','T')+'Z');return Number.isNaN(d.valueOf())?'':d.toLocaleString('lv-LV',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});}
function statusText(status) {return ({pending:'Gaida vērtējumu',approved:'Apstiprināts',rejected:'Noraidīts'})[status]||status;}
function drawScores(containerId) {
  $(containerId).innerHTML = data.leaderboard.map(row=>`<div class="leader-row"><div class="rank-num ${row.rank<=3?'top':''}">${row.rank<=3?['🥇','🥈','🥉'][row.rank-1]:`#${row.rank}`}</div><div class="leader-name">${esc(row.name)}</div><div class="leader-tasks">${row.done} uzd.</div><div class="leader-points">${row.points} <small>p.</small></div></div>`).join('') || '<div class="admin-empty">Nav pievienotu komandu.</div>';
}
function renderAdmin() {
  if (!data) return;
  $('loginScreen').classList.add('hidden');$('dashboard').classList.remove('hidden');
  const pending=data.submissions.filter(x=>x.status==='pending').length;
  $('pendingBubble').textContent=pending?pending:'';
  $('statCards').innerHTML=[['KOMANDAS',data.teams.length,''],['UZDEVUMI',data.tasks.length,''],['IESNIEGTIE FOTO',data.submissions.length,''],['GAIDA PĀRBAUDI',pending,'highlight']].map(([name,n,cls])=>`<div class="stat-card ${cls}"><span class="stat-label">${name}</span><strong>${n}</strong></div>`).join('');
  $('submissionsList').innerHTML=data.submissions.map(s=>`<article class="submission-item"><a href="${s.photo_url}" target="_blank" rel="noopener"><img loading="lazy" class="submission-image" src="${s.photo_url}" alt="${esc(s.team_name)} iesūtītais foto"></a><div class="submission-info"><div class="submission-meta"><span class="status-chip ${esc(s.status)}">${statusText(s.status)}</span><span>${fmtDate(s.created_at)}</span></div><h3>${esc(s.task_title)}</h3><p>Komanda: <strong>${esc(s.team_name)}</strong> · ${s.points} punkti</p>${s.note?`<p>📝 ${esc(s.note)}</p>`:''}<div class="review-buttons"><button class="accept" type="button" data-review="approved" data-id="${s.id}">✓ Apstiprināt</button><button class="reject" type="button" data-review="rejected" data-id="${s.id}">✕ Noraidīt</button></div></div></article>`).join('') || '<div class="admin-empty">Iesniegto fotogrāfiju vēl nav. Komandas tās šeit redzēs uzreiz pēc iesniegšanas.</div>';
  $('adminTaskList').innerHTML=data.tasks.map((task,idx)=>`<div class="admin-list-row"><div class="admin-row-left"><span class="admin-row-emoji">${esc(task.emoji)}</span><div><h3>#${idx+1} ${esc(task.title)} <span class="points-label">+${task.points} P</span></h3><p>${esc(task.description)}</p>${task.has_reference?`<p><a class="reference-link" href="/api/reference/${task.id}" target="_blank" rel="noopener">Parauga attēls ↗</a></p>`:''}</div></div><div class="admin-list-actions"><button class="outline-btn" data-reference="${task.id}">🖼️ ${task.has_reference?'Mainīt attēlu':'Parauga attēls'}</button>${task.has_reference?`<button class="outline-btn" data-delete-reference="${task.id}">✕ Attēls</button>`:''}<button class="outline-btn" data-edit="${task.id}">Labot</button><button class="outline-btn danger-btn" data-delete-task="${task.id}">Dzēst</button></div></div>`).join('')||'<div class="admin-empty">Nav uzdevumu. Izveido pirmo!</div>';
  $('addTaskBtn').disabled=data.tasks.length>=10;
  $('addTaskBtn').title=data.tasks.length>=10?'Sasniegts 10 uzdevumu limits':'';
  $('adminTeamList').innerHTML=data.teams.map(t=>`<div class="admin-list-row"><div><h3>👥 ${esc(t.name)}</h3><p>Komandas piekļuves kods</p></div><div class="admin-list-actions"><span class="team-code">${esc(t.code)}</span><button class="outline-btn" data-copy="${esc(t.code)}">Kopēt</button><button class="outline-btn danger-btn" data-delete-team="${t.id}">Dzēst</button></div></div>`).join('')||'<div class="admin-empty">Pievieno pirmo komandu!</div>';
  $('addTeamForm').querySelector('button').disabled=data.teams.length>=10;
  drawScores('adminLeaderboard');
}
async function refresh() {
  try {data=await api('/api/admin/state');renderAdmin();}
  catch(err) {if (!data){$('loginScreen').classList.remove('hidden');$('dashboard').classList.add('hidden');}}
}
$('adminLoginForm').addEventListener('submit',async e=>{
  e.preventDefault();$('adminLoginMessage').textContent='';
  const button=e.currentTarget.querySelector('button');button.disabled=true;
  try{await api('/api/admin/login',json('POST',{password:$('adminPassword').value}));$('adminPassword').value='';await refresh();toast('Organizatora panelis atvērts.');}
  catch(err){$('adminLoginMessage').textContent=err.message;}
  finally{button.disabled=false;}
});
$('adminLogout').addEventListener('click',async()=>{await api('/api/admin/logout',{method:'POST'});data=null;await refresh();toast('Tu izgāji no administratora paneļa.');});
document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(t=>{t.classList.toggle('active',t===tab);t.setAttribute('aria-selected',String(t===tab));});
  document.querySelectorAll('.tab-content').forEach(section=>section.classList.toggle('hidden',section.id!==tab.dataset.tab+'Tab'));
}));
$('submissionsList').addEventListener('click',async e=>{
  const btn=e.target.closest('[data-review]');if(!btn)return;
  const decision=btn.dataset.review;
  const note=decision==='rejected'?prompt('Noraidīšanas iemesls (komanda to redzēs):','Foto neatbilst uzdevumam.') : '';
  if(note===null)return;
  btn.disabled=true;
  try{await api(`/api/admin/review/${btn.dataset.id}`,json('POST',{decision,note}));await refresh();toast(decision==='approved'?'Foto apstiprināts! Punkti piešķirti.':'Foto noraidīts. Komanda var mēģināt vēlreiz.');}
  catch(err){toast(err.message);}finally{btn.disabled=false;}
});
function openEditor(task=null){
  editTaskId=task?.id??null;
  $('taskDialogHeading').textContent=task?'Labot uzdevumu':'Jauns uzdevums';
  $('editTitle').value=task?.title??'';
  $('editDescription').value=task?.description??'';
  $('editPoints').value=task?.points??100;
  $('editEmoji').value=task?.emoji??'📸';
  $('editCategory').value=['Poza','Objekts','Vieta','Komanda','Radošais','Foto'].includes(task?.category)?task.category:'Foto';
  $('taskEditMessage').textContent='';$('taskDialog').showModal();
}
$('addTaskBtn').addEventListener('click',()=>openEditor());
$('taskEditForm').addEventListener('submit',async e=>{
  e.preventDefault();const button=$('saveTaskBtn');button.disabled=true;
  const payload={title:$('editTitle').value.trim(),description:$('editDescription').value.trim(),points:Number($('editPoints').value),emoji:$('editEmoji').value.trim()||'📸',category:$('editCategory').value};
  try{await api(editTaskId?`/api/admin/tasks/${editTaskId}`:'/api/admin/tasks',json(editTaskId?'PUT':'POST',payload));$('taskDialog').close();await refresh();toast('Uzdevums saglabāts.');}
  catch(err){$('taskEditMessage').textContent=err.message;}finally{button.disabled=false;}
});
const referenceInput=document.createElement('input');referenceInput.type='file';referenceInput.accept='image/*';referenceInput.className='file-input';referenceInput.setAttribute('aria-label','Parauga attēls');document.body.appendChild(referenceInput);
let referenceTaskId=null;
referenceInput.addEventListener('change',async()=>{
  const file=referenceInput.files?.[0];if(!file||!referenceTaskId)return;
  const form=new FormData();form.append('file',file);
  try{await api(`/api/admin/tasks/${referenceTaskId}/reference`,{method:'POST',body:form});await refresh();toast('Parauga attēls pievienots.');}
  catch(err){toast(err.message);}
  referenceInput.value='';referenceTaskId=null;
});
$('adminTaskList').addEventListener('click',async e=>{
  const btn=e.target.closest('button');if(!btn)return;
  if(btn.dataset.edit){openEditor(data.tasks.find(t=>t.id===Number(btn.dataset.edit)));return;}
  if(btn.dataset.reference){referenceTaskId=Number(btn.dataset.reference);referenceInput.click();return;}
  if(btn.dataset.deleteReference){
    if(!confirm('Noņemt parauga attēlu?'))return;
    try{await api(`/api/admin/tasks/${btn.dataset.deleteReference}/reference`,{method:'DELETE'});await refresh();toast('Parauga attēls noņemts.');}catch(err){toast(err.message);}return;
  }
  if(btn.dataset.deleteTask){
    if(!confirm('Dzēst šo uzdevumu? (Uzdevumus ar iesniegtiem foto dzēst nevar.)'))return;
    try{await api(`/api/admin/tasks/${btn.dataset.deleteTask}`,{method:'DELETE'});await refresh();toast('Uzdevums dzēsts.');}catch(err){toast(err.message);}
  }
});
$('addTeamForm').addEventListener('submit',async e=>{
  e.preventDefault();const input=$('newTeamName');
  try{await api('/api/admin/teams',json('POST',{name:input.value.trim()}));input.value='';await refresh();toast('Komanda izveidota! Nokopē tās kodu.');}
  catch(err){toast(err.message);}
});
$('adminTeamList').addEventListener('click',async e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.dataset.copy){
    try{await navigator.clipboard.writeText(button.dataset.copy);toast('Komandas kods nokopēts.');}
    catch(err){toast(`Kods: ${button.dataset.copy}`);}return;
  }
  if(button.dataset.deleteTeam){
    if(!confirm('Dzēst šo komandu? (Komandas ar iesniegumiem dzēst nevar.)'))return;
    try{await api(`/api/admin/teams/${button.dataset.deleteTeam}`,{method:'DELETE'});await refresh();toast('Komanda dzēsta.');}catch(err){toast(err.message);}
  }
});
setInterval(()=>{if(data)refresh();},12000);
refresh();
