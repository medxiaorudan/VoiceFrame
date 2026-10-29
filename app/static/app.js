const $ = id => document.getElementById(id);
const state = { project: null, projects: [], jobs: [], step: 'media', dirty: false, selected: null, result: null, upload: false, language: localStorage.getItem('voiceframe.language') || 'zh', system: null };
const t = (zh, en) => state.language === 'zh' ? zh : en;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const media = path => `/media/${state.project.id}/${path.split('/').map(encodeURIComponent).join('/')}`;
const seconds = value => Number(value || 0).toFixed(2);
const time = value => `${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`;
let toastTimer;
function toast(message, error = false) { clearTimeout(toastTimer); $('toast').textContent = message; $('toast').className = `toast${error?' error':''}`; $('toast').hidden = false; toastTimer = setTimeout(() => $('toast').hidden = true, error ? 14000 : 4500); }
async function api(path, options = {}) {
  if (options.body && !(options.body instanceof FormData)) { options.headers = {'Content-Type':'application/json', ...options.headers}; options.body = JSON.stringify(options.body); }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if(response.status === 401 && !$('login-dialog').open) $('login-dialog').showModal();
    const detail = Array.isArray(data.detail) ? data.detail.map(x => `${x.loc?.slice(1).join('.')}: ${x.msg}`).join('\n') : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}
function act(fn) { return async event => { try { await fn(event); } catch(error) { toast(error.message, true); } }; }
function localize() {
  document.documentElement.lang = state.language === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-zh]').forEach(node => node.textContent = state.language === 'zh' ? node.dataset.zh : node.dataset.en);
  $('language').textContent = state.language === 'zh' ? 'EN' : '中文';
  $('new-name').placeholder = t('例如：子集个数 · 第一课', 'e.g. Subsets · Lesson one');
  for (const id of ['instruction', 'rules']) $(id).placeholder = inputExample(id);
  renderSidebar();
  if(state.project) { renderStatus(); renderCues(); renderJobs(); detectionOptions(); }
}
function dirty() { state.dirty = true; renderStatus(); }
function renderStatus() {
  const p = state.project; if (!p) { $('save').disabled = true; return; }
  $('save').disabled = !state.dirty || state.upload;
  $('save-state').textContent = state.dirty ? t('有未保存的更改', 'Unsaved changes') : t('✓ 已保存', '✓ Saved');
  const approved = !state.dirty && p.approved_revision === p.revision;
  $('approval-badge').textContent = approved ? t('✓ 预览已确认', '✓ Preview approved') : t('待确认预览', 'Preview not approved');
  $('approval-badge').className = `badge${approved?' good':''}`;
  $('export').disabled = !approved || busy();
  $('export-note').textContent = approved ? t('准备好了，可以生成完整视频。', 'All set. Render the complete video.') : t('先生成并确认当前配置的预览。修改设置后需重新确认。', 'Generate and approve a preview first. Changes require a new approval.');
  const preview = currentPreview();
  $('approve').disabled = !preview || state.dirty;
  ['preview','audition','detect'].forEach(id => $(id).disabled = busy());
  $('project-meta').textContent = p.video ? `${time(p.video.duration)} · ${p.cues.length} ${t('条字幕','cues')} · ${t('版本','Revision')} ${p.revision}` : t('上传视频，开始创作。','Upload your video to get started.');
  $('selected-cue').textContent = state.selected ? t(`已选择第 ${state.selected} 条字幕。暂停在字幕刚出现的画面，再点击校准。`, `Cue ${state.selected} selected. Pause at its first visible frame, then align.`) : t('先点击左侧字幕序号选择一句。','Select a cue number on the left first.');
}
function busy() { return state.upload || state.jobs.some(j => ['queued','running'].includes(j.status)); }
function currentPreview() { return state.jobs.find(j => j.kind === 'preview' && j.status === 'completed' && j.request.revision === state.project.revision); }
function renderSidebar() {
  $('project-list').innerHTML = state.projects.map(p => `<button class="project-item ${p.id===state.project?.id?'active':''}" data-project="${p.id}"><span>▤</span><span>${esc(p.name)}</span></button>`).join('') || `<p class="helper">${t('你的项目会出现在这里。','Your projects will appear here.')}</p>`;
}
async function listProjects() { state.projects = await api('/api/projects'); renderSidebar(); }
async function openProject(id) {
  if(state.dirty && !confirm(t('离开会丢失未保存的更改。继续吗？','Leave and discard unsaved changes?'))) return;
  state.project = await api(`/api/projects/${id}`); state.dirty = false; state.selected = state.project.cues[0]?.id; state.result = null;
  state.jobs = await api(`/api/projects/${id}/jobs`);
  localStorage.setItem('voiceframe.project',id);
  $('welcome').hidden = true; $('workspace').hidden = false;
  fillProject(); renderSidebar(); setStep(state.project.video ? (state.project.cues.length?'voice':'media') : 'media');
}
function fillProject() {
  const p = state.project, s = p.settings;
  $('project-name').value = p.name; $('breadcrumb').textContent = p.name;
  for(const [id, field] of Object.entries({engine:'engine','voice-mode':'mode',speaker:'speaker','voice-language':'language',instruction:'instruction','reference-text':'reference_text',offset:'offset','max-speed':'max_speed'})) $(id).value = s[field];
  $('rules').value = s.rules.map(r => `${r.source} => ${r.replacement}`).join('\n');
  $('reference-player').hidden = !p.reference;
  if(p.reference) $('reference-player').src = media(p.reference.file);
  $('drop-zone').hidden = !!p.video; $('video-wrap').hidden = !p.video;
  if(p.video) { $('player').src = media(p.video.file); $('video-info').textContent = `${p.video.name} · ${time(p.video.duration)}`; }
  else { $('player').removeAttribute('src'); $('video-info').textContent = t('尚未上传视频','No video uploaded'); }
  $('stream').innerHTML = (p.video?.streams || []).filter(s => s.type==='subtitle').map(s=>`<option value="${s.index}">${s.index} · ${esc(s.codec)} · ${esc(s.language)}</option>`).join('') || `<option value="">${t('未检测到字幕轨','No subtitle tracks')}</option>`;
  voiceOptions(); detectionOptions(); renderCues(); renderJobs(); renderStatus();
}
function readSettings() {
  const rules = $('rules').value.split('\n').filter(l=>l.trim()).map(line=>{
    const index = line.indexOf('=>');
    if(index<1 || !line.slice(index+2).trim()) throw new Error(t('发音规则格式应为：原文 => 读法','Use pronunciation rules in this format: source => spoken form'));
    return {source:line.slice(0,index).trim(),replacement:line.slice(index+2).trim()};
  });
  return {...state.project.settings, engine:$('engine').value, mode:$('voice-mode').value, speaker:$('speaker').value, language:$('voice-language').value, instruction:$('instruction').value, reference_text:$('reference-text').value, offset:Number($('offset').value), max_speed:Number($('max-speed').value), rules};
}
async function save() {
  if(!state.project || !state.dirty) return;
  const p = state.project;
  state.project = await api(`/api/projects/${p.id}`, {method:'PUT',body:{revision:p.revision,name:$('project-name').value.trim(),cues:p.cues,settings:readSettings()}});
  state.dirty = false; $('breadcrumb').textContent = state.project.name; await listProjects(); renderStatus();
}
function setStep(step) { state.step = step; document.querySelectorAll('[data-step]').forEach(b=>b.classList.toggle('active',b.dataset.step===step)); ['media','voice','sync','export'].forEach(s=>$(`settings-${s}`).hidden=s!==step); }
function voiceOptions() { const ref = $('voice-mode').value==='reference'; $('preset-options').hidden=ref; $('reference-options').hidden=!ref; }
function detectionOptions() { const d=$('detection').value; $('ocr-options').hidden=d!=='ocr'; $('stream-options').hidden=d!=='extract'; $('detect-note').textContent=d==='extract'?t('读取视频封装中的文本字幕轨。烧录在画面里的文字请选择 OCR。','Reads a text track inside the video container. Use OCR for text burned into the picture.'):d==='ocr'?t('按设定间隔识别裁剪区域中的文字。需要安装 Tesseract。','Samples visible text in the selected crop. Requires Tesseract.'):t('从原音轨识别讲话，不代表画面字幕。需要 faster-whisper。','Recognizes speech from the original soundtrack, not on-screen text. Requires faster-whisper.'); }
function renderCues() {
  const cues=state.project.cues; $('caption-empty').hidden=!!cues.length;
  $('cue-list').innerHTML=cues.map(c=>`<article class="cue ${state.selected===c.id?'active':''}" data-cue="${c.id}"><button class="cue-number" data-seek="${c.id}" aria-label="${t('跳转到字幕','Seek to cue')} ${c.id}">${c.id}</button><div><div class="cue-times"><input aria-label="${t('开始秒数','Start seconds')}" data-field="start" type="number" min="0" step=".01" value="${seconds(c.start)}"><span>→</span><input aria-label="${t('结束秒数','End seconds')}" data-field="end" type="number" min="0" step=".01" value="${seconds(c.end)}"><span>s</span><button data-delete="${c.id}" aria-label="${t('删除字幕','Delete cue')}">×</button></div><textarea rows="1" data-field="text" aria-label="${t('字幕原文','Original subtitle')}">${esc(c.text)}</textarea><textarea class="spoken-input" rows="1" data-field="spoken_text" aria-label="${t('实际读法','Spoken text')}" placeholder="${t('自定义读法（留空则沿用原文与词典）','Spoken override (leave blank to use text + dictionary)')}">${esc(c.spoken_text)}</textarea></div></article>`).join('');
}
function showResult(job) {
  if(!job?.result) return;
  if(job.result.video) { state.result=job; $('player').src=media(job.result.video); $('show-result').classList.add('selected'); $('show-source').classList.remove('selected'); $('video-wrap').hidden=false; $('drop-zone').hidden=true; }
  else if(job.result.audio) { $('audition-player').src=media(job.result.audio); $('audition-player').hidden=false; }
}
function renderJobs() {
  const names={voice:t('音色试听','Voice audition'),preview:t('画面试听','Video preview'),final:t('最终视频','Final render'),extract:t('字幕轨提取','Subtitle extraction'),ocr:t('画面字幕识别','Caption OCR'),transcribe:t('原声转写','Transcription')};
  const statuses={queued:t('排队中','Queued'),running:t('处理中','Running'),completed:t('已完成','Completed'),failed:t('需要处理','Needs attention'),cancelled:t('已取消','Cancelled'),interrupted:t('已中断','Interrupted')};
  $('job-count').textContent=state.jobs.length;
  $('jobs').innerHTML=state.jobs.map(j=>`<article class="job"><div class="job-title"><strong>${names[j.kind]}</strong><span class="job-status">${statuses[j.status]}</span></div>${['running','queued'].includes(j.status)?`<div class="progress"><div style="width:${Math.round(j.progress*100)}%"></div></div>`:''}<div class="job-stage">${esc(j.stage)} ${j.status==='running'?`${Math.round(j.progress*100)}%`:''}</div>${j.error?`<p class="job-error">${esc(j.error)}</p>`:''}${j.result?.issues?`<p class="job-error">${j.result.issues.map(c=>`#${c.id}: ${seconds(c.original)}s / ${seconds(c.window)}s`).join(' · ')}</p>`:''}<div class="job-actions">${j.status==='completed'&&(j.result?.video||j.result?.audio)?`<button class="text-button" data-play="${j.id}">${t('播放结果','Play result')}</button>`:''}${['running','queued'].includes(j.status)?`<button class="text-button" data-cancel="${j.id}">${t('取消','Cancel')}</button>`:''}${['failed','cancelled','interrupted'].includes(j.status)?`<button class="text-button" data-retry="${j.id}">${t('重试','Retry')}</button>`:''}${j.result?.report?`<a href="${media(j.result.report)}" download>${t('下载诊断','Download report')}</a>`:''}${j.result?.subtitles&&j.kind!=='preview'&&j.kind!=='final'?`<a href="${media(j.result.subtitles)}" download>${t('下载识别字幕','Download detected SRT')}</a>`:''}</div></article>`).join('') || `<p class="muted">${t('生成任务会显示在这里。','Your jobs will appear here.')}</p>`;
  const final=state.jobs.find(j=>j.kind==='final'&&j.status==='completed'&&j.request.revision===state.project.revision);
  $('downloads').innerHTML=final?['video','audio','subtitles'].map(k=>`<a href="${media(final.result[k])}" download>↓ ${k==='video'?'MP4':k==='audio'?'WAV':'SRT'} · ${t('下载成品','Download')}</a>`).join(''):'';
}
async function refreshJobs() {
  if(!state.project) return;
  const pid=state.project.id;
  const jobs=await api(`/api/projects/${pid}/jobs`);
  if(state.project?.id!==pid) return;
  const finished=jobs.filter(j=>j.status==='completed' && state.jobs.some(old=>old.id===j.id&&old.status!=='completed'));
  state.jobs=jobs; renderJobs(); renderStatus();
  for(const j of finished) {
    if(['extract','ocr','transcribe'].includes(j.kind)&&!state.dirty) { state.project=await api(`/api/projects/${pid}`); fillProject(); }
    else showResult(j);
    toast(t('任务已完成。','Your job is ready.'));
  }
}
async function startJob(kind) {
  await save();
  if(busy()) throw new Error(t('请等待当前任务完成或先取消。','Wait for the current job or cancel it first.'));
  const body={kind,revision:state.project.revision,text:$('voice-test-text').value,start:Number($('preview-start').value),duration:Number($('preview-duration').value),stream_index:Number($('stream').value||0),crop_top:Number($('crop-top').value),crop_bottom:Number($('crop-bottom').value),interval:Number($('ocr-interval').value)};
  await api(`/api/projects/${state.project.id}/jobs`,{method:'POST',body}); await refreshJobs(); toast(t('任务已加入队列，完成后会显示结果。','Job queued. Results will appear when ready.'));
}
async function uploadFile(kind,file) {
  if(!file||!state.project) return; await save(); state.upload=true;renderStatus();
  const pid=state.project.id;
  try {
    const data=new FormData();data.append('file',file);data.append('revision',state.project.revision);
    const result=await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',`/api/projects/${pid}/${kind}`);xhr.upload.onprogress=e=>{if(e.lengthComputable){const percent=Math.round(100*e.loaded/e.total);$('save-state').textContent=`${t('上传中','Uploading')} ${percent}%`;toast(`${t('上传中','Uploading')} ${percent}%`);}};xhr.onerror=()=>reject(new Error(t('上传中断，请重试。','Upload interrupted. Please retry.')));xhr.onload=()=>{let body;try{body=JSON.parse(xhr.responseText);}catch{reject(new Error('Invalid server response'));return;}if(xhr.status>=200&&xhr.status<300)resolve(body);else reject(new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail)));};xhr.send(data);});
    if(state.project?.id===pid){state.project=result;state.dirty=false;fillProject();}
    toast(t('上传完成。','Upload complete.'));
  } finally {state.upload=false;renderStatus();}
}
document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>setStep(b.dataset.step));
document.querySelectorAll('.next-step').forEach(b=>b.onclick=act(async()=>{await save();setStep(b.dataset.next);}));
$('language').onclick=()=>{state.language=state.language==='zh'?'en':'zh';localStorage.setItem('voiceframe.language',state.language);localize();};
for(const id of ['new-project','welcome-create']) $(id).onclick=()=>$('create-dialog').showModal();
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('create-form').onsubmit=act(async e=>{e.preventDefault();if(state.dirty)await save();const p=await api('/api/projects',{method:'POST',body:{name:$('new-name').value.trim()}});$('create-dialog').close();$('new-name').value='';await listProjects();await openProject(p.id);});
$('project-list').onclick=act(async e=>{const b=e.target.closest('[data-project]');if(b)await openProject(b.dataset.project);});
$('save').onclick=act(save);
for(const id of ['project-name','engine','voice-mode','speaker','voice-language','instruction','reference-text','offset','max-speed','rules']) $(id).addEventListener('input',()=>{dirty();if(id==='voice-mode')voiceOptions();});
$('detection').onchange=detectionOptions;
$('cue-list').addEventListener('input',e=>{const row=e.target.closest('[data-cue]');if(!row||!e.target.dataset.field)return;const c=state.project.cues.find(c=>c.id===Number(row.dataset.cue));const f=e.target.dataset.field;c[f]=['start','end'].includes(f)?Number(e.target.value):e.target.value;dirty();});
$('cue-list').onclick=e=>{const seek=e.target.closest('[data-seek]');if(seek){state.selected=Number(seek.dataset.seek);const c=state.project.cues.find(c=>c.id===state.selected);if(state.result){$('player').src=media(state.project.video.file);state.result=null;$('player').addEventListener('loadedmetadata',()=>$('player').currentTime=Math.max(0,c.start+Number($('offset').value)),{once:true});}else $('player').currentTime=Math.max(0,c.start+Number($('offset').value));$('show-source').classList.add('selected');$('show-result').classList.remove('selected');renderCues();renderStatus();}const remove=e.target.closest('[data-delete]');if(remove){state.project.cues=state.project.cues.filter(c=>c.id!==Number(remove.dataset.delete));dirty();renderCues();}};
$('add-cue').onclick=()=>{const last=state.project.cues.at(-1);const start=last?.end||0;state.project.cues.push({id:Math.max(0,...state.project.cues.map(c=>c.id))+1,start,end:Math.min(start+2,state.project.video?.duration||start+2),text:t('在这里输入字幕','Enter caption here'),spoken_text:''});dirty();renderCues();$('cue-list').scrollTop=$('cue-list').scrollHeight;};
$('replace-video').onclick=()=>$('video-file').click();$('drop-zone').onclick=()=>$('video-file').click();$('drop-zone').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('video-file').click();}};
$('drop-zone').ondragover=e=>{e.preventDefault();$('drop-zone').classList.add('drag');};$('drop-zone').ondragleave=()=>$('drop-zone').classList.remove('drag');$('drop-zone').ondrop=act(async e=>{e.preventDefault();$('drop-zone').classList.remove('drag');await uploadFile('video',e.dataTransfer.files[0]);});
$('upload-subtitles').onclick=()=>$('subtitle-file').click();$('upload-reference').onclick=()=>$('reference-file').click();
for(const [id,kind] of [['video-file','video'],['subtitle-file','subtitles'],['reference-file','reference']]) $(id).onchange=act(async e=>{await uploadFile(kind,e.target.files[0]);e.target.value='';});
$('detect').onclick=act(()=>startJob($('detection').value));$('audition').onclick=act(()=>startJob('voice'));$('preview').onclick=act(()=>startJob('preview'));$('export').onclick=act(()=>startJob('final'));
$('anchor').onclick=act(async()=>{if(!state.selected)throw new Error(t('请先选择一条字幕。','Select a cue first.'));if(state.result)throw new Error(t('请切回原视频再校准。','Switch to the original video to calibrate.'));const c=state.project.cues.find(c=>c.id===state.selected);$('offset').value=($('player').currentTime-c.start).toFixed(2);dirty();toast(t('偏移已设置，请生成新预览检查。','Offset set. Generate a preview to check it.'));});
$('use-time').onclick=()=>{$('preview-start').value=($('player').currentTime+(state.result?.result.start||0)).toFixed(2);};
$('approve').onclick=act(async()=>{const j=currentPreview();if(!j||state.dirty)throw new Error(t('先生成当前配置的预览。','Generate a current preview first.'));state.project=await api(`/api/projects/${state.project.id}/approve`,{method:'POST',body:{job_id:j.id}});renderStatus();setStep('export');});
$('show-source').onclick=()=>{if(!state.project?.video)return;state.result=null;$('player').src=media(state.project.video.file);$('show-source').classList.add('selected');$('show-result').classList.remove('selected');};
$('show-result').onclick=()=>{const j=currentPreview()||state.jobs.find(j=>j.kind==='preview'&&j.status==='completed');if(j)showResult(j);else toast(t('还没有生成预览。','No preview generated yet.'));};
$('jobs').onclick=act(async e=>{const play=e.target.closest('[data-play]');if(play)showResult(state.jobs.find(j=>j.id===play.dataset.play));const cancel=e.target.closest('[data-cancel]');if(cancel){await api(`/api/jobs/${cancel.dataset.cancel}/cancel`,{method:'POST'});await refreshJobs();}const retry=e.target.closest('[data-retry]');if(retry){await api(`/api/jobs/${retry.dataset.retry}/retry`,{method:'POST'});await refreshJobs();}});
$('system-button').onclick=act(async()=>{const s=await api('/api/system');state.system=s;$('system-info').innerHTML=`<p>${esc(s.platform)} · ${esc(s.architecture)} · ${esc(s.engine)}</p>${['ffmpeg','ffprobe','mlx','torch','ocr','asr'].map(k=>`<div class="system-row"><span>${k.toUpperCase()}</span><span>${s[k]?'✓':t('未安装','Not installed')}</span></div>`).join('')}<p>${t('在项目虚拟环境中安装语音引擎：','Install the speech engine in the project virtual environment:')}</p><code>python scripts/install_engine.py --engine ${esc(s.engine)}</code><p>${t('首次生成会下载模型。Windows / Linux 建议 NVIDIA GPU；CPU 模式较慢。详见 README。','First generation downloads model weights. NVIDIA GPU is recommended on Windows/Linux; CPU mode is slow. See README.')}</p>`;$('system-dialog').showModal();});
$('login-dialog').addEventListener('cancel',e=>e.preventDefault());
$('login-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{method:'POST',body:{token:$('access-key').value}});$('access-key').value='';$('login-dialog').close();await init();}catch(err){$('login-error').textContent=err.message;}};
window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
async function init() {localize();const session=await api('/api/session');if(!session.authenticated){$('login-dialog').showModal();return;}await listProjects();const last=localStorage.getItem('voiceframe.project');if(state.projects.some(p=>p.id===last))await openProject(last);renderStatus();}
setInterval(()=>refreshJobs().catch(()=>{}),2000);
init().catch(error=>toast(error.message,true));

// Examples are editable text; unsupported control tags are never inserted.
function inputExample(id) {
  if (id === 'rules') return t('银行 => 银航\n重新 => 虫新\n2^n => 二的恩次幂', 'VoiceFrame => Voice Frame\n2^n => two to the power of n');
  if (id === 'instruction') return t('用自然的普通话讲解。短语内部连贯朗读，逗号处稍作停顿，句号处停顿更明显，在完整句子之间自然换气。', 'Explain naturally. Link words smoothly within phrases, pause briefly at commas and more fully at sentence endings, and breathe naturally between complete sentences.');
  return '';
}
function completeExample(field, force = false) {
  const example = inputExample(field.id);
  if (!example || field.disabled || field.readOnly) return false;
  const value = field.value;
  if (!force && value && (!example.startsWith(value) || value === example || field.selectionStart !== value.length || field.selectionEnd !== value.length)) return false;
  if (force && value && !example.startsWith(value) && !confirm(t('用示例替换当前内容？', 'Replace this field with the example?'))) return false;
  field.value = example;
  field.focus();
  field.setSelectionRange(force ? 0 : value.length, example.length);
  field.dispatchEvent(new Event('input', {bubbles: true}));
  return true;
}
document.addEventListener('keydown', e => {
  if (e.key !== 'Tab' || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || e.isComposing) return;
  if (['rules', 'instruction'].includes(e.target.id) && completeExample(e.target)) e.preventDefault();
});
document.querySelectorAll('[data-fill-example]').forEach(button => {
  button.onclick = () => completeExample($(button.dataset.fillExample), true);
});
