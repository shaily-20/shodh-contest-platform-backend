from fastapi.responses import HTMLResponse


def page_html() -> HTMLResponse:
    return HTMLResponse(content="""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shodh Contest Platform</title>
  <style>
    :root { --ink:#172033; --muted:#68708a; --brand:#635bff; --panel:#fff; --line:#e7e9f2; --bg:#f5f6fb; }
    * { box-sizing:border-box } body { margin:0; font-family:Inter,system-ui,sans-serif; color:var(--ink); background:var(--bg) }
    header { height:72px; display:flex; align-items:center; justify-content:space-between; padding:0 32px; background:white; border-bottom:1px solid var(--line) }
    .brand { font-weight:800; font-size:21px } .brand span { color:var(--brand) }
    .shell { max-width:1180px; margin:28px auto; padding:0 20px }
    .grid { display:grid; grid-template-columns:280px 1fr; gap:20px }
    .card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:0 8px 24px rgba(30,35,90,.04) }
    h1,h2,h3 { margin-top:0 } h1 { font-size:28px } h2 { font-size:18px }
    input, textarea, select, button { width:100%; padding:11px 12px; border:1px solid var(--line); border-radius:9px; font:inherit }
    textarea { min-height:200px; resize:vertical; font-family:"SFMono-Regular",Consolas,monospace }
    button { cursor:pointer; border:0; background:var(--brand); color:white; font-weight:700 }
    button.secondary { background:#eef0ff; color:#4640b8 } button.danger { background:#fff1f1; color:#b42318 }
    .field { margin:10px 0 } label { display:block; font-size:13px; font-weight:700; margin-bottom:6px }
    .muted { color:var(--muted) } .hidden { display:none !important } .tabs { display:flex; gap:8px; margin-bottom:16px }
    .tabs button { width:auto } .contest { padding:14px; border:1px solid var(--line); border-radius:12px; margin:10px 0; cursor:pointer }
    .contest.active { border-color:var(--brand); background:#f8f7ff } .row { display:flex; gap:10px } .row>* { flex:1 }
    .status { display:inline-block; padding:5px 9px; border-radius:999px; background:#eef0ff; font-size:12px; font-weight:800 }
    pre { white-space:pre-wrap; background:#151929; color:#eef1ff; padding:14px; border-radius:10px }
    #toast { position:fixed; right:24px; bottom:24px; max-width:380px; background:#172033; color:white; padding:12px 16px; border-radius:10px; opacity:0; transform:translateY(12px); transition:.2s }
    #toast.show { opacity:1; transform:translateY(0) }
  </style>
</head>
<body>
<header><div class="brand">SHODH <span>ARENA</span></div><div id="account"><button class="secondary" style="width:auto" onclick="showAuth()">Sign in</button></div></header>
<div class="shell">
  <div id="authView" class="grid hidden">
    <div></div>
    <div class="card" style="max-width:480px">
      <h1>Welcome to Shodh</h1><p class="muted">Register or sign in to join contests and submit code.</p>
      <div class="tabs"><button id="loginTab" onclick="setAuthMode('login')">Sign in</button><button id="registerTab" class="secondary" onclick="setAuthMode('register')">Register</button></div>
      <div class="field"><label>Username</label><input id="authUser" autocomplete="username" /></div>
      <div id="nameField" class="field hidden"><label>Display name</label><input id="authName" /></div>
      <div class="field"><label>Password</label><input id="authPassword" type="password" autocomplete="current-password" /></div>
      <div id="keyField" class="field hidden"><label>Organizer key <span class="muted">(optional)</span></label><input id="authKey" /></div>
      <button onclick="submitAuth()" id="authSubmit">Sign in</button>
    </div>
  </div>

  <div id="appView" class="hidden">
    <h1>Contests</h1>
    <div class="grid">
      <aside class="card"><h2>Available contests</h2><div id="contests"><p class="muted">Loading...</p></div></aside>
      <main class="card">
        <div id="contestPanel"><h2>Select a contest</h2><p class="muted">Choose a contest to view its problems.</p></div>
        <div id="workPanel" class="hidden">
          <div class="row"><div><label>Problem</label><select id="problemSelect" onchange="showProblem()"></select></div><button class="secondary" style="align-self:end" onclick="joinContest()">Join contest</button></div>
          <div id="problemStatement"></div>
          <label>Python solution</label><textarea id="code" spellcheck="false"># Write your Python solution here
</textarea>
          <div class="row"><button onclick="submitCode()">Submit solution</button><button class="secondary" onclick="checkSubmission()">Check latest status</button></div>
          <div id="result" style="margin-top:14px"></div>
        </div>
      </main>
    </div>
  </div>
</div>
<div id="toast"></div>
<script>
let token=localStorage.getItem('shodh_token')||'', user=JSON.parse(localStorage.getItem('shodh_user')||'null'), contests=[], selected=null, problems=[], submissionId=null, authMode='login';
const api=(path,options={})=>fetch(path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...(options.headers||{})}}).then(async r=>{const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.detail||'Request failed'); return d});
function toast(s){const t=document.getElementById('toast');t.textContent=s;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),3200)}
function setAuthMode(m){authMode=m;document.getElementById('nameField').classList.toggle('hidden',m==='login');document.getElementById('keyField').classList.toggle('hidden',m==='login');document.getElementById('loginTab').className=m==='login'?'':'secondary';document.getElementById('registerTab').className=m==='register'?'':'secondary';document.getElementById('authSubmit').textContent=m==='login'?'Sign in':'Create account'}
function showAuth(){document.getElementById('appView').classList.add('hidden');document.getElementById('authView').classList.remove('hidden');setAuthMode(authMode)}
async function submitAuth(){try{const body=authMode==='login'?{external_id:authUser.value,password:authPassword.value}:{external_id:authUser.value,display_name:authName.value||authUser.value,password:authPassword.value,organizer_key:authKey.value||null};const d=await api(authMode==='login'?'/auth/token':'/auth/register',{method:'POST',body:JSON.stringify(body)});token=d.access_token;user=d;localStorage.setItem('shodh_token',token);localStorage.setItem('shodh_user',JSON.stringify(user));renderAccount();openApp()}catch(e){toast(e.message)}}
function renderAccount(){const el=document.getElementById('account');el.innerHTML=user?`<div><b>${escapeHtml(user.display_name)}</b> <span class="muted">${escapeHtml(user.role)}</span> <button class="danger" style="width:auto;margin-left:8px" onclick="logout()">Sign out</button></div>`:`<button class="secondary" style="width:auto" onclick="showAuth()">Sign in</button>`}
function logout(){token='';user=null;localStorage.removeItem('shodh_token');localStorage.removeItem('shodh_user');renderAccount();showAuth()}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function openApp(){document.getElementById('authView').classList.add('hidden');document.getElementById('appView').classList.remove('hidden');await loadContests()}
async function loadContests(){try{contests=await api('/contests');const el=document.getElementById('contests');el.innerHTML=contests.length?contests.map(c=>`<div class="contest" onclick="selectContest(${c.id})"><b>${escapeHtml(c.title)}</b><br><span class="muted">Ends ${new Date(c.ends_at).toLocaleString()}</span></div>`).join(''):'<p class="muted">No contests yet.</p>'}catch(e){toast(e.message)}}
async function selectContest(id){selected=contests.find(c=>c.id===id);document.queryAll?.();document.querySelectorAll('.contest').forEach((x,i)=>x.classList.toggle('active',contests[i].id===id));document.getElementById('contestPanel').innerHTML=`<h2>${escapeHtml(selected.title)}</h2><p class="muted">${new Date(selected.starts_at).toLocaleString()} – ${new Date(selected.ends_at).toLocaleString()}</p>`;document.getElementById('workPanel').classList.remove('hidden');try{problems=await api('/organizations/'+selected.organization_id+'/problems');document.getElementById('problemSelect').innerHTML=problems.map(p=>`<option value="${p.id}">${escapeHtml(p.title)}</option>`).join('');showProblem()}catch(e){toast(e.message)}}
function showProblem(){const p=problems.find(x=>x.id===Number(document.getElementById('problemSelect').value));if(p)document.getElementById('problemStatement').innerHTML=`<h3>${escapeHtml(p.title)}</h3><pre>${escapeHtml(p.statement)}</pre>`}
async function joinContest(){try{await api('/contests/'+selected.id+'/join',{method:'POST'});toast('You joined the contest')}catch(e){toast(e.message)}}
async function submitCode(){try{if(!selected)return toast('Select a contest first');const problemId=Number(document.getElementById('problemSelect').value);const d=await api('/contests/'+selected.id+'/submissions',{method:'POST',body:JSON.stringify({problem_id:problemId,language:'python',code:document.getElementById('code').value,idempotency_key:'ui-'+crypto.randomUUID()})});submissionId=d.id;showResult(d);toast('Submission queued')}catch(e){toast(e.message)}}
async function checkSubmission(){try{if(!submissionId)return toast('Submit code first');const d=await api('/submissions/'+submissionId);showResult(d)}catch(e){toast(e.message)}}
function showResult(d){document.getElementById('result').innerHTML=`<div><span class="status">${escapeHtml(d.status)}</span> ${d.verdict?'<b>'+escapeHtml(d.verdict)+'</b>':''}</div>`}
renderAccount();if(token&&user)openApp();else showAuth();
</script>
</body>
</html>
""
)
