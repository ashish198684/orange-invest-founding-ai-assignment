"""G5: authentic Playwright Chromium *screen capture* of a real local demo.

No mocked browser responses or fabricated results. Optional captions are labelled
as recording annotations; all actions hit the real locally-running G4 API/provider.
Creates a fresh synthetic user in the existing demo realm without resetting data.
"""
import argparse,json,subprocess,time,shutil,uuid
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
PROJECT='orange-g4-demo-b6d4bb72'
BASE='http://127.0.0.1:8080'

def run():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['groq','scripted'],default='groq')
    p.add_argument('--label',default='g5_authentic_walkthrough')
    a=p.parse_args()
    out=ROOT/'artifacts'/'demo';out.mkdir(parents=True,exist_ok=True)
    uid='g5-video-'+uuid.uuid4().hex[:10]
    setup=subprocess.run(['docker','compose','--project-name',PROJECT,'exec','-T','api','python','-X','utf8','scripts/g4_fixture.py','--user',uid],cwd=ROOT,capture_output=True,text=True,timeout=25)
    if setup.returncode:raise RuntimeError('unable_to_create_test_user:'+setup.stderr[:140])
    seed=json.loads(setup.stdout)
    assert seed['user']==uid and seed['password']=='synthetic-test'
    started=time.monotonic();chapters=[];stage='startup';passed=False;video_path=None
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(out),
            record_video_size={'width':1440,'height':900},timezone_id='Asia/Kolkata',
            color_scheme='light')
        page=context.new_page()
        video=page.video
        started=time.monotonic()  # Video begins with this page, not with browser startup.
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            def caption(title,desc='',seconds=0):
                nonlocal stage
                stage=title
                chapters.append({'at_seconds':round(time.monotonic()-started,1),'stage':title})
                print('CHAPTER',round(time.monotonic()-started,1),title,flush=True)
                page.evaluate("""([title,desc])=>{
                  let el=document.getElementById('g5-screen-note');
                  if(!el){el=document.createElement('div');el.id='g5-screen-note';
                    el.style.cssText='position:fixed;bottom:14px;left:50%;transform:translateX(-50%);width:max-content;max-width:82vw;z-index:99999;background:rgba(13,24,35,.91);border:1px solid rgba(255,255,255,.2);color:#fff;padding:12px 18px;border-radius:12px;box-shadow:0 6px 25px rgba(0,0,0,.25);pointer-events:none;font:600 14px/1.4 Arial,sans-serif;text-align:center';
                    document.body.appendChild(el)}
                  el.textContent='RECORDED DEMO ANNOTATION  ·  '+title+(desc?' — '+desc:'')
                }""",[title,desc])
                if seconds:page.wait_for_timeout(int(seconds*1000))
            page.goto(BASE)
            caption('01 / User experience','real local Chromium workspace; mock providers',8)
            page.locator('#username').fill(uid)
            page.locator('#password').fill('synthetic-test')
            page.get_by_role('button',name='Open workspace').click()
            expect(page.locator('#workspace')).to_be_visible(timeout=15000)
            caption('02 / Governed agent','side-by-side chat and real trace; user owns approvals',10)
            page.locator('#interpreter').select_option(a.mode)
            request=('Please help with my leaking kitchen tap: a plumber in Indiranagar this week, mornings only, with a ceiling of eighteen hundred rupees.'
              if a.mode=='groq' else 'Find a plumber in Indiranagar this week, mornings only, under ₹1,800.')
            page.locator('#message').fill(request);page.locator('#send').click()
            expect(page.locator('.provider').first).to_be_visible(timeout=28000)
            if a.mode=='groq':expect(page.locator('#mode')).to_contain_text('openai/gpt-oss-20b',timeout=20000)
            caption('03 / Real model proposal','model interprets constraints; provider search remains deterministic',16)
            page.locator('.provider').first.get_by_role('button',name='Read reviews (untrusted)',exact=True).click()
            expect(page.locator('.review').first).to_contain_text(__import__('re').compile('system',__import__('re').I),timeout=10000)
            caption('04 / Prompt injection boundary','third-party review displayed as untrusted text, never authority',12)
            page.locator('.slots button').first.click()
            expect(page.locator('.approval-card')).to_be_visible(timeout=15000)
            previous=page.locator('.approval-card button').get_attribute('data-approval-id')
            caption('05 / Immutable approval card','exact provider, slot, and hold quote; no booking yet',14)
            page.locator('#message').fill('Change only the spending cap to nineteen hundred rupees, keeping everything else.' if a.mode=='groq' else 'Actually budget under ₹1,900.')
            page.locator('#send').click()
            expect(page.locator('.provider').first).to_be_visible(timeout=25000)
            expect(page.locator('.approval-card')).to_have_count(0,timeout=20000)
            caption('06 / One-fact correction','outdated approval revoked; unchanged constraints preserved',15)
            page.locator('.slots button').first.click()
            expect(page.locator('.approval-card')).to_be_visible(timeout=15000)
            assert page.locator('.approval-card button').get_attribute('data-approval-id')!=previous
            card=page.locator('.approval-card').inner_text()
            caption('07 / Explicit consent','user must click a new exact approval before any write',13)
            page.locator('.approval-card button').click()
            expect(page.locator('#status')).to_have_text('BOOKED',timeout=35000)
            expect(page.locator('#trace')).to_contain_text('provider timeout',timeout=12000)
            caption('08 / The hard failure','provider committed; response timed out; status readback proves success',24)
            page.locator('#trace').evaluate('(el)=>{el.scrollTop=el.scrollHeight}')  # Stable container survives live trace refresh.
            page.wait_for_timeout(6000)
            page.reload();expect(page.locator('#status')).to_have_text('BOOKED',timeout=20000)
            expect(page.locator('.booking')).to_have_count(1)
            caption('09 / Durable restart','same confirmed booking after browser reload',10)
            page.locator('#memory-key').select_option('area')
            page.locator('#memory-value').fill('Indiranagar')
            page.get_by_role('button',name='Remember',exact=True).click()
            expect(page.locator('#memories')).to_contain_text('Indiranagar',timeout=10000)
            page.locator('#memories').get_by_role('button',name='Correct',exact=True).click()
            page.locator('#memory-value').fill('Koramangala')
            page.get_by_role('button',name='Remember',exact=True).click()
            expect(page.locator('#memories')).to_contain_text('Koramangala',timeout=10000)
            page.locator('#memories').get_by_role('button',name='Forget',exact=True).click()
            expect(page.locator('#memories')).to_contain_text('Forgotten',timeout=10000)
            caption('10 / Memory agency','scoped preference corrected, then explicitly forgotten',18)
            journeys=page.request.get(BASE+'/workflows').json()
            wid=next(w['workflow_id'] for w in journeys if w['status']=='BOOKED')
            csrf=page.evaluate("sessionStorage.getItem('orange-csrf')")
            options=page.request.post(BASE+'/workflows/'+wid+'/search',data={},headers={'Origin':BASE,'X-CSRF-Token':csrf}).json()
            provider=next(p for p in options if p['id'] in card)
            target=provider['free_slots'][0]
            page.locator('.booking input').fill(target[:16])
            page.get_by_role('button',name='Reschedule',exact=True).click()
            expect(page.locator('.approval-card')).to_contain_text('Review reschedule',timeout=15000)
            caption('11 / New approval for reschedule','no previous consent carries forward',12)
            page.locator('.approval-card button').click()
            expect(page.locator('#status')).to_have_text('RESCHEDULED',timeout=35000)
            caption('12 / Verified reschedule','readback shows the new confirmed slot',14)
            page.get_by_role('button',name='Cancel appointment',exact=True).click()
            expect(page.locator('.approval-card')).to_contain_text('Review cancellation',timeout=15000)
            caption('13 / Cancellation consent','separate card and stable operation key',12)
            page.locator('.approval-card button').click()
            expect(page.locator('#status')).to_have_text('CANCELLED',timeout=35000)
            caption('14 / Verified cancellation','provider readback; real user-visible state',14)
            # Preserve live desktop-scale chat and trace for the closing scene.
            page.get_by_role('button',name='Sign out',exact=True).click()
            expect(page.locator('#login-panel')).to_be_visible(timeout=15000)
            caption('15 / Session revoked','logged-out session expires; audit references remain',8)
            elapsed=time.monotonic()-started
            if elapsed<190:
                caption('G5 demonstration complete','recorded browser, real mock-provider ledger and real traces',190-elapsed)
            elif elapsed>300:
                print('DURATION_WARNING: actual run exceeds five minutes',elapsed,flush=True)
            assert not errors,errors
            passed=True
        except Exception as exc:
            print('VIDEO_JOURNEY_ERROR',stage,type(exc).__name__,str(exc)[:800],flush=True)
            raise
        finally:
            context.close();browser.close()
            source=Path(video.path())
            duration=time.monotonic()-started
            filename=a.label+'_'+a.mode+('_PASS' if passed else '_FAILED')+'.webm'
            target=out/filename
            shutil.copyfile(source,target)
            rec={'status':'PASS' if passed and 180<=duration<=300 else 'FAIL',
                'browser':'real Playwright Chromium screen recording','video_path':str(target),'mode':a.mode,
                'duration_seconds':round(duration,2),'file_bytes':target.stat().st_size,
                'source_commit':'b6d4bb72e5108e691fe38d1dfc994cf7dae8771c',
                'demo_project':PROJECT,'synthetic_user':uid,'chapters':chapters,
                'browser_errors':errors,'failure_stage':None if passed else stage,
                'notes':'Video records real G4 app/provider actions. On-screen labels are DEMO ANNOTATIONS; provider and payments are mock.'}
            (out/(a.label+'_'+a.mode+'_receipt.json')).write_text(json.dumps(rec,indent=2),encoding='utf-8')
            print('VIDEO_RECEIPT',json.dumps({k:rec[k] for k in ['status','duration_seconds','file_bytes','video_path','mode','failure_stage']}),flush=True)
        if not passed or not 180<=duration<=300:raise SystemExit(1)

if __name__=='__main__':run()
