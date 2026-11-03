'use strict';
const $ = id => document.getElementById(id);
const state = {user:null, csrf:sessionStorage.getItem('orange-csrf'), wid:null, logical:null, card:null, op:null, busy:false, memory:[], seen:new Set(), prices:{}};
const money = n => n == null ? 'Price unavailable from provider contract' : new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(n);
const when = iso => iso ? new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kolkata'}).format(new Date(iso))+' IST' : '—';
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function button(text,fn,cls){const b=el('button',text,cls);b.type='button';b.onclick=()=>work(fn);return b;}
function notice(text){$('notice').textContent=text;$('notice').hidden=false;clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('notice').hidden=true,9000);}
function say(text,role='assistant'){if(!text)return;const b=el('div',text,'bubble '+role);$('chat-log').append(b);$('chat-log').scrollTop=$('chat-log').scrollHeight;}
function fail(error){notice(error.message||'Connection interrupted. Reconnect to the same request.');$('connection').textContent='Reconnect available';}
async function api(method,path,value){
 const headers={'Content-Type':'application/json'};if(method!=='GET')headers['X-CSRF-Token']=state.csrf||'';
 const response=await fetch(path,{method,headers,credentials:'same-origin',body:value===undefined?undefined:JSON.stringify(value),signal:AbortSignal.timeout(20000)});
 const data=await response.json();
 if(!response.ok){const error=new Error((data.message||'Request denied')+' ('+(data.error||response.status)+')');error.code=data.error;throw error;}
 $('connection').textContent='Connected';return data;
}
function work(fn){state.queue=(state.queue||Promise.resolve()).then(async()=>{state.busy=true;$('send').disabled=true;try{await fn();}catch(e){fail(e);}finally{state.busy=false;$('send').disabled=false;}});return state.queue;}
function rememberJourney(){sessionStorage.setItem('orange-journey-'+state.user,JSON.stringify({wid:state.wid,logical:state.logical,op:state.op}));}
function clearCard(){state.card=null;$('approval').replaceChildren();$('approval').hidden=true;}
function showDraft(w){$('status').textContent=w.status.replaceAll('_',' ');const d=w.draft;const node=$('draft');node.replaceChildren(el('strong','CURRENT PLAN · REVISION '+w.revision));node.append(el('span',[d.service,d.area,d.date_window?when(d.date_window.start)+' → '+when(d.date_window.end):null,d.budget_inr!=null?'Budget '+money(d.budget_inr):null].filter(Boolean).join(' · ')));if(d.preferences&&Object.keys(d.preferences).length)node.append(el('div',Object.entries(d.preferences).map(([k,v])=>k.replaceAll('_',' ')+': '+v).join(' · ')));node.hidden=false;}
async function create(){if(!state.logical){state.logical=crypto.randomUUID();rememberJourney();}const w=await api('POST','/workflows',{logical_request_id:state.logical,draft:{}});state.wid=w.workflow_id;rememberJourney();return w;}
function newRequest(){state.wid=null;state.logical=crypto.randomUUID();state.op=null;state.seen.clear();state.prices={};clearCard();$('providers').replaceChildren();$('draft').hidden=true;$('status').textContent='Ready';$('chat-log').replaceChildren();$('trace').replaceChildren(el('li','Your activity will appear here.','empty'));$('trace-raw').textContent='No run yet.';rememberJourney();say('What would you like to arrange? Your existing appointments stay in the list below.');$('message').focus();}
async function chat(text){
 if(!state.wid)await create();
 clearCard();$('providers').replaceChildren();say(text,'user');
 const mode=$('interpreter').value;if(mode==='groq')$('mode').textContent='Groq · Verifying response…';
 let result;
 try{result=await api('POST','/workflows/'+state.wid+'/chat',{text,mode});}
 catch(error){if(mode==='groq')$('mode').textContent='Groq · Unavailable / unverified';throw error;}
 if(mode==='groq'&&result.model?.verified){$('mode').textContent='Groq · '+result.model.model_id+' · Verified';$('mode').title=Math.round(result.model.latency_ms)+' ms · actual validated response';}
 else $('mode').textContent='Scripted · Offline';
 showDraft(result.workflow);say(result.question?.message||result.message);
 if(result.action_proposal&&result.action_proposal!=='plan'){await bookings();$('bookings').scrollIntoView({block:'center'});}
 else if(!result.question)await search();await activity();
}
async function search(){
 if(!state.wid)throw new Error('Tell me the service, area and time first.');
 const rows=await api('POST','/workflows/'+state.wid+'/search',{});const target=$('providers');target.replaceChildren();
 if(!rows.length){say('No providers match this plan. You can change the budget, area or time.');return;}
 target.append(el('p',rows.length+' providers match your plan. Select a slot to see its exact quote.','muted'));
 for(const p of rows){state.prices[p.id]=p.price;const card=el('article',undefined,'provider');const head=el('div',undefined,'provider-head');head.append(el('strong',p.attributes.technician+' · '+p.id),el('strong',money(p.price)));card.append(head,el('p','★ '+p.rating+' · '+p.attributes.area+' · Search price; final quote follows.'));card.append(button('Read reviews (untrusted)',async()=>{const d=await api('GET','/providers/'+p.id);let reviews=card.querySelector('.review');if(reviews){reviews.remove();return;}reviews=el('div',undefined,'review');reviews.append(el('strong','PROVIDER REVIEWS · UNTRUSTED DATA'));for(const r of d.reviews)reviews.append(el('p',r.text));reviews.append(el('p','Reviews cannot authorize actions or change your preferences.'));card.append(reviews);await activity();}));
 const slots=el('div',undefined,'slots');for(const slot of p.free_slots.slice(0,9))slots.append(button(when(slot),async()=>{clearCard();const a=await api('POST','/workflows/'+state.wid+'/hold',{provider_id:p.id,slot});await loadCard(a.approval_id);await refreshJourney(false);}));if(!p.free_slots.length)slots.append(el('p','No matching slots currently available.'));card.append(slots);target.append(card);}
 await activity();
}
async function loadCard(aid){
 const card=await api('GET','/approvals/'+aid);state.card=card;const s=card.snapshot;const box=el('article',undefined,'approval-card');box.append(el('p','YOUR APPROVAL IS REQUIRED','eyebrow'),el('h3',s.action==='book'?'Review your booking':s.action==='cancel'?'Review cancellation':'Review reschedule'));
 const dl=el('dl');const fields=[['Action',s.action],['Provider',s.provider_id],...(s.old_slot?[['Current slot',when(s.old_slot)]]:[]),['New slot',s.action==='cancel'?'No new appointment':when(s.new_slot)],['Price',money(s.price_amount)],['Price status',s.price_status.replaceAll('_',' ')],['Expires',when(s.expires_at)]];if(s.booking_id)fields.push(['Booking',s.booking_id]);for(const [k,v] of fields){dl.append(el('dt',k),el('dd',v));}box.append(dl);
 if(s.action!=='book')box.append(el('p','Original verified price shown where available. The fixed mock charges no new fee; no fresh provider quote is available.','muted'));
 if(state.prices[s.provider_id]!=null&&s.price_amount!==state.prices[s.provider_id])box.append(el('p','Quote changed: search '+money(state.prices[s.provider_id])+' → hold '+money(s.price_amount)+'. Approve only this current quote.','drift'));
 box.append(el('p','Revision '+card.revision+' · Fingerprint '+card.fingerprint+' · Card '+card.card_id,'approval-meta'));
 const confirm=button('Approve '+s.action+' · '+(s.price_amount==null?'price unavailable':money(s.price_amount)),async()=>{
  if(state.card!==card)throw new Error('This card has been replaced. Review the current quote.');
  confirm.disabled=true;
  try{const pending=await api('POST','/approvals/'+card.approval_id+'/confirm',{card_id:card.card_id,fingerprint:card.fingerprint,revision:card.revision,snapshot:card.snapshot});state.op=pending.operation_id;rememberJourney();clearCard();say(pending.message);await refreshJourney(false);}
  catch(error){clearCard();say('Confirmation could not be verified. Reconnect to the same request before trying again.');await refreshJourney(false);throw error;}
 },'primary');confirm.dataset.approvalId=aid;box.append(confirm);$('approval').replaceChildren(box);$('approval').hidden=false;$('providers').replaceChildren();
}
async function refreshJourney(announce=true){
 if(!state.wid){await memory();await bookings();return;}
 const w=await api('GET','/workflows/'+state.wid);showDraft(w);
 const current=w.operations.find(o=>o.approval_id===w.current_approval_id)||w.operations.find(o=>o.operation_id===state.op)||w.operations.find(o=>o.result?.status===w.status)||w.operations.at(-1);
 if(current){state.op=current.operation_id;rememberJourney();}
 if(w.status==='AWAITING_APPROVAL'&&w.current_approval_id){if(state.card?.approval_id!==w.current_approval_id)await loadCard(w.current_approval_id);}
 else clearCard();
 if(state.op){const result=await api('GET','/operations/'+state.op);$('status').textContent=result.status.replaceAll('_',' ');const signature=state.op+':'+result.status;if(!state.seen.has(signature)){state.seen.add(signature);say(result.message||result.reason||'Provider outcome is not yet verified.');if(['BOOKED','CANCELLED','RESCHEDULED'].includes(result.status))await bookings();}}
 else if(announce)say('Reconnected to the same request. Current state: '+w.status.replaceAll('_',' ')+'.');
 await activity();
}
async function activity(){
 if(!state.wid)return;const rows=await api('GET','/activity/'+state.wid);const list=$('trace');list.replaceChildren();
 const visible=rows.filter(e=>!['request_start'].includes(e.event_type)&&!(e.event_type==='run_exit'&&e.tool_call_count===0&&e.model_call_count===0&&!e.state_after));
 for(const e of visible.slice(-45)){const item=el('li');item.append(el('strong',(e.tool_name?e.tool_name+' · ':'')+e.event_type.replaceAll('_',' ')),el('small',[e.state_after||e.status||e.error_class,e.decision_reason,e.duration_ms!=null?Math.round(e.duration_ms)+' ms':null].filter(Boolean).join(' · ')),el('small','Run '+e.run_id.slice(0,8)+' · '+new Date(e.timestamp).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})));list.append(item);}
 if(!list.children.length)list.append(el('li','Request received. Awaiting activity.','empty'));$('trace-raw').textContent=JSON.stringify(rows.slice(-15),null,2);list.scrollTop=list.scrollHeight;
}
async function memory(){
 const rows=await api('GET','/memory');state.memory=rows;const host=$('memories');host.replaceChildren();
 for(const r of rows){const item=el('div',undefined,'memory-row');const value=r.value_json==null?null:JSON.parse(r.value_json);item.append(el('strong',r.key.replaceAll('_',' ')+': '+(r.forgotten?'Forgotten':String(value))),el('small',r.provenance.replaceAll('_',' ')+' · '+(r.confirmed?'confirmed':'awaiting confirmation')+' · version '+r.version));
 if(!r.forgotten){item.append(button('Correct',async()=>{$('memory-key').value=r.key;$('memory-value').value=value;$('memory-value').focus();notice('Edit the value, then select Remember to save a new version.');}));item.append(button('Forget',async()=>{await api('POST','/memory',{key:r.key,value:null,event_id:crypto.randomUUID(),expected_version:r.version,forget:true});await memory();if(state.wid)await refreshJourney(false);notice('Preference forgotten and excluded from future retrieval.');}));if(!r.confirmed)item.append(button('Confirm preference',async()=>{await api('POST','/memory',{key:r.key,value:null,event_id:crypto.randomUUID(),expected_version:r.version,confirm:true});await memory();}));}host.append(item);}
 if(!rows.length)host.append(el('p','No saved preferences yet.','muted'));
}
async function change(booking,action,newSlot){
 newRequest();await create();const a=await api('POST','/workflows/'+state.wid+'/change',{action,booking_id:booking.id,...(newSlot?{new_slot:newSlot}: {})});await loadCard(a.approval_id);await refreshJourney(false);$('approval').scrollIntoView({behavior:'smooth',block:'center'});
}
async function bookings(){
 const rows=await api('GET','/bookings');const host=$('bookings');host.replaceChildren();
 for(const b of rows){const row=el('article',undefined,'booking');const title=el('div');title.append(el('strong',b.service+' · '+b.provider),el('small',when(b.slot)+' · '+b.status),el('small','Booking '+b.id));row.append(title);
 if(b.status==='booked'){const actions=el('div',undefined,'booking-actions');const date=el('input');date.type='datetime-local';date.setAttribute('aria-label','New appointment date and time in IST');date.value=b.slot.slice(0,16);actions.append(date,button('Reschedule',()=>{if(!date.value)throw new Error('Choose a new date and time.');return change(b,'reschedule',date.value+':00+05:30');}),button('Cancel appointment',()=>change(b,'cancel')));row.append(actions);}host.append(row);}
 if(!rows.length)host.append(el('p','No appointments yet. Start with a request above.','muted'));
}
async function enter(session){state.user=session.username;$('account').textContent=state.user;$('mode').textContent=session.mode==='scripted'?'Scripted · Offline':session.mode+' · '+session.model_id;$('mode').title=session.verification;$('login-panel').hidden=true;$('workspace').hidden=false;$('signout').hidden=false;const saved=JSON.parse(sessionStorage.getItem('orange-journey-'+state.user)||'{}');Object.assign(state,saved);await memory();await bookings();if(state.wid)await refreshJourney();}
$('login-form').onsubmit=e=>{e.preventDefault();work(async()=>{const session=await api('POST','/login',{username:$('username').value,password:$('password').value});state.csrf=session.csrf_token;sessionStorage.setItem('orange-csrf',state.csrf);$('password').value='';await enter(await api('GET','/session'));});};
$('chat-form').onsubmit=e=>{e.preventDefault();const text=$('message').value.trim();if(text)work(async()=>{await chat(text);$('message').value='';});};
$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}};
$('new-request').onclick=()=>work(newRequest);$('search').onclick=()=>work(search);$('refresh').onclick=()=>work(()=>refreshJourney());$('memory-refresh').onclick=()=>work(memory);$('bookings-refresh').onclick=()=>work(bookings);
$('interpreter').onchange=()=>{$('mode').textContent=$('interpreter').value==='groq'?'Groq · Awaiting live verification':'Scripted · Offline';notice($('interpreter').value==='groq'?'Live Groq interprets your next message. Approval remains a separate action.':'Offline scripted interpretation selected.');};
$('memory-form').onsubmit=e=>{e.preventDefault();work(async()=>{const key=$('memory-key').value;const old=state.memory.find(r=>r.key===key);const value=key==='earliest_hour'?Number($('memory-value').value):$('memory-value').value;await api('POST','/memory',{key,value,expected_version:old?.version||0,event_id:crypto.randomUUID()});$('memory-value').value='';await memory();notice('Preference saved with your confirmation.');});};
$('signout').onclick=()=>work(async()=>{await api('POST','/logout',{});sessionStorage.removeItem('orange-csrf');location.reload();});
setInterval(()=>{if(state.user&&state.wid&&!state.busy)work(()=>refreshJourney(false));},3500);
if(state.csrf)work(async()=>{try{await enter(await api('GET','/session'));}catch{sessionStorage.removeItem('orange-csrf');state.csrf=null;}});
