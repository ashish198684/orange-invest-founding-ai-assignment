"""Real Chromium acceptance: idle polls must never disable the Send button.

Runs against the persistent demo via a unique disposable synthetic test user.
Never resets existing database volumes, touches alice, or logs credentials.
"""
import argparse, datetime, json, subprocess, time, uuid, re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8080'
API='orange-g4-demo-b6d4bb72-api-1'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',required=True)
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--base-url',default=BASE)
    parser.add_argument('--api-container',default=API)
    parser.add_argument('--forward-to-port',type=int,default=None)
    args=parser.parse_args()
    out=ROOT/'artifacts'/'receipts'/args.label
    out.mkdir(parents=True,exist_ok=False)
    user='g5poll-'+uuid.uuid4().hex[:12]
    fixture=subprocess.run(['docker','exec',args.api_container,'python','-X','utf8','scripts/g4_fixture.py','--user',user],capture_output=True,text=True,timeout=40)
    assert fixture.returncode==0, 'synthetic_user_setup_failed'
    report={'status':'RUNNING','mode':'full' if args.full else 'poll_only','user':user,
            'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source':'real Chrome + API + PostgreSQL; never mocked page requests',
            'idle_disabled_transitions':[],'checks':[]}
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1400,'height':950},timezone_id='Asia/Kolkata')
        if args.forward_to_port:
            # Transparent real HTTP forwarding, not mocked responses. Browser origin
            # stays 127.0.0.1:8080; isolated API uses a different host port.
            pattern='http://127.0.0.1:8080/**'
            context.route(pattern,lambda route: route.continue_(url=route.request.url.replace(':8080',':'+str(args.forward_to_port),1)))
            report['isolated_real_http_target']='127.0.0.1:'+str(args.forward_to_port)
        page=context.new_page()
        browser_errors=[]
        page.on('pageerror',lambda e:browser_errors.append(str(e)))
        try:
            report['api_http_events']=[]
            def capture_http(response):
                if response.request.resource_type!='fetch':return
                # Do not call response.json() inside a synchronous response callback:
                # it can wait for requestfinished and deadlock this browser test.
                report['api_http_events'].append({'method':response.request.method,'status':response.status,
                    'endpoint':'/'+response.url.split('://',1)[-1].split('/',1)[-1].split('/')[0]})
            page.on('response',capture_http)
            page.goto(args.base_url,wait_until='domcontentloaded')
            page.locator('#username').fill(user)
            page.locator('#password').fill('synthetic-test')
            page.get_by_role('button',name='Open workspace').click()
            expect(page.locator('#workspace')).to_be_visible(timeout=15000)
            page.locator('#interpreter').select_option('scripted')
            page.locator('#message').fill('Find a plumber in Indiranagar this week, mornings only, under 1800.')
            page.locator('#send').click()
            expect(page.locator('.provider').first).to_be_visible(timeout=22000)
            expect(page.locator('#send')).to_be_enabled()
            report['checks'].append('full plan and provider query completed')
            page.evaluate("""() => {
                window.__g5PollChanges = [];
                const b = document.getElementById('send');
                new MutationObserver(() => {
                  window.__g5PollChanges.push({ms:Math.round(performance.now()),disabled:b.disabled});
                }).observe(b,{attributes:true,attributeFilter:['disabled']});
            }""")
            # The 3500ms poll occurs more than three times while the user is idle.
            page.wait_for_timeout(14500)
            report['idle_disabled_transitions']=page.evaluate('window.__g5PollChanges')
            report['idle_poll_seconds']=14.5
            page.screenshot(path=str(out/'idle_poll.png'),full_page=True)
            assert len(report['idle_disabled_transitions'])==0, (
                'Send disabled '+str(len(report['idle_disabled_transitions']))+' times during idle polling')
            report['checks'].append('Send stays enabled across >3 idle polls')
            if args.full:
                page.locator('#message').fill('Change only my budget to under 1900.')
                page.locator('#send').click()
                expect(page.locator('.provider').first).to_be_visible(timeout=20000)
                report['checks'].append('foreground request still functions after polling')
                page.locator('.provider').first.get_by_role('button',name='Read reviews (untrusted)').click()
                expect(page.locator('.review').first).to_be_visible(timeout=10000)
                report['checks'].append('untrusted review displayed without permission mutation')
                page.locator('.slots button').first.click()
                expect(page.locator('.approval-card')).to_be_visible(timeout=15000)
                assert page.locator('#status').inner_text()=='AWAITING APPROVAL'
                report['checks'].append('exact approval card required before booking')
                page.locator('.approval-card button').click()
                expect(page.locator('#status')).to_have_text('BOOKED',timeout=35000)
                expect(page.locator('#trace')).to_contain_text('provider timeout',timeout=10000)
                page.get_by_role('button',name='Refresh appointments',exact=True).click() if page.get_by_role('button',name='Refresh appointments',exact=True).count() else None
                expect(page.locator('.booking')).to_have_count(1,timeout=15000)
                report['checks'].append('timeout-after-success reconciled into exactly one booking')
            assert not browser_errors,browser_errors
            report['status']='PASS'
        except Exception as exc:
            report['status']='FAIL'
            report['error']=str(exc)[:1000]
            report['ui_status']=page.locator('#status').inner_text() if page.locator('#status').count() else None
            report['notice']=page.locator('#notice').inner_text() if page.locator('#notice').count() and page.locator('#notice').is_visible() else None
            page.screenshot(path=str(out/'failure.png'),full_page=True)
            raise
        finally:
            report['browser_errors']=browser_errors
            report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
            context.close()
            browser.close()
            print('G5_POLL_ACCEPTANCE',json.dumps({'status':report['status'],'idle_transitions':len(report['idle_disabled_transitions']),'checks':report['checks'],'error':report.get('error')}),flush=True)

if __name__=='__main__': main()
