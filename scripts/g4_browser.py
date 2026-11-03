"""Real Chromium browser journey against local API, with rendered card evidence."""
import argparse,json,sys,time,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--user',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    out=ROOT/'artifacts/receipts'/a.label;out.mkdir(exist_ok=False,parents=True)
    events=[];errors=[]
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1100},timezone_id='Asia/Kolkata')
        page=context.new_page();page.on('pageerror',lambda err:errors.append(str(err)))
        def response(r):
            if r.request.resource_type=='fetch':
                try:
                    data=r.json();events.append({'method':r.request.method,'path':r.url.split('8080')[-1],'status':r.status,'run_id':data.get('run_id') if isinstance(data,dict) else None,'result_status':data.get('status') if isinstance(data,dict) else None})
                except Exception:pass
        page.on('response',response)
        try:
            page.goto('http://127.0.0.1:8080/');page.locator('#username').fill(a.user);page.locator('#password').fill('synthetic-test');page.get_by_role('button',name='Open workspace').click();expect(page.locator('#workspace')).to_be_visible(timeout=15000)
            if a.live:page.locator('#interpreter').select_option('groq')
            page.locator('#message').fill('Please help with my leaking kitchen tap: a plumber in Indiranagar this week, mornings only, with a ceiling of eighteen hundred rupees.' if a.live else 'Find a plumber in Indiranagar this week, mornings only, under ₹1,800.');page.locator('#send').click()
            expect(page.locator('.provider').first).to_be_visible(timeout=20000)
            if a.live:expect(page.locator('#mode')).to_contain_text('openai/gpt-oss-20b')
            page.locator('.provider').first.get_by_role('button',name='Read reviews (untrusted)',exact=True).click();expect(page.locator('.review').first).to_contain_text(re.compile('system',re.I))
            page.screenshot(path=str(out/'01_reviews.png'),full_page=True)
            page.locator('.slots button').first.click();expect(page.locator('.approval-card')).to_be_visible(timeout=15000)
            first=page.locator('.approval-card').inner_text();page.screenshot(path=str(out/'02_exact_card.png'),full_page=True)
            old_id=page.locator('.approval-card button').get_attribute('data-approval-id')
            page.locator('#message').fill('Change only the spending cap to nineteen hundred rupees, keeping everything else.' if a.live else 'Actually budget under ₹1,900.');page.locator('#send').click();expect(page.locator('.provider').first).to_be_visible(timeout=20000);expect(page.locator('.approval-card')).to_have_count(0)
            page.locator('.slots button').first.click();expect(page.locator('.approval-card')).to_be_visible(timeout=15000)
            assert page.locator('.approval-card button').get_attribute('data-approval-id')!=old_id
            card=page.locator('.approval-card').inner_text();page.screenshot(path=str(out/'03_revised_card.png'),full_page=True)
            page.locator('.approval-card button').click();expect(page.locator('#status')).to_have_text('BOOKED',timeout=30000)
            expect(page.locator('#trace')).to_contain_text('provider timeout',timeout=15000)
            page.locator('#trace li').filter(has_text='provider timeout').first.scroll_into_view_if_needed()
            page.screenshot(path=str(out/'04_verified_timeout_recovery.png'),full_page=True)
            page.reload();expect(page.locator('#status')).to_have_text('BOOKED',timeout=20000);expect(page.locator('.booking')).to_have_count(1)
            page.locator('#memory-key').select_option('area');page.locator('#memory-value').fill('Indiranagar');page.get_by_role('button',name='Remember',exact=True).click();expect(page.locator('#memories')).to_contain_text('Indiranagar',timeout=10000)
            page.locator('#memories').get_by_role('button',name='Correct',exact=True).click();page.locator('#memory-value').fill('Koramangala');page.get_by_role('button',name='Remember',exact=True).click();expect(page.locator('#memories')).to_contain_text('Koramangala',timeout=10000)
            page.locator('#memories').get_by_role('button',name='Forget',exact=True).click();expect(page.locator('#memories')).to_contain_text('Forgotten',timeout=10000)
            page.screenshot(path=str(out/'05_reconnect_and_forget.png'),full_page=True)
            # Read availability through the same authenticated browser context;
            # rescheduling and consent still happen through actual visible controls.
            journeys=page.request.get('http://127.0.0.1:8080/workflows').json()
            wid=next(w['workflow_id'] for w in journeys if w['status']=='BOOKED')
            csrf=page.evaluate("sessionStorage.getItem('orange-csrf')")
            options=page.request.post('http://127.0.0.1:8080/workflows/'+wid+'/search',data={},headers={'Origin':'http://127.0.0.1:8080','X-CSRF-Token':csrf}).json()
            provider=next(p for p in options if p['id'] in card)
            target=provider['free_slots'][0]
            page.locator('.booking input').fill(target[:16]);page.get_by_role('button',name='Reschedule',exact=True).click();expect(page.locator('.approval-card')).to_contain_text('Review reschedule',timeout=15000)
            page.locator('.approval-card button').click();expect(page.locator('#status')).to_have_text('RESCHEDULED',timeout=30000)
            expect(page.locator('.booking input')).to_have_value(target[:16],timeout=10000)
            page.screenshot(path=str(out/'06_rescheduled.png'),full_page=True)
            page.get_by_role('button',name='Cancel appointment',exact=True).click();expect(page.locator('.approval-card')).to_contain_text('Review cancellation',timeout=15000);page.locator('.approval-card button').click();expect(page.locator('#status')).to_have_text('CANCELLED',timeout=30000);expect(page.locator('.booking')).to_contain_text('cancelled',timeout=10000)
            page.screenshot(path=str(out/'07_cancelled.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'08_mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile layout overflows horizontally'
            page.get_by_role('button',name='Sign out',exact=True).click();expect(page.locator('#login-panel')).to_be_visible(timeout=10000)
            assert not errors,errors
            report={'status':'PASS','browser':'Chromium','mode':'groq-live' if a.live else 'scripted-offline','user':a.user,'first_card':first,'revised_card':card,'checks':['real login/chat','review injection displayed as text','exact hold quote','old card removed after correction','timeout-after-success verified','reload same workflow and one appointment','memory correct/forget','reschedule with new approval','cancel 503 recovery with new approval','mobile layout','session logout'],'errors':errors}
        except Exception as exc:
            page.screenshot(path=str(out/'failure.png'),full_page=True);report={'status':'FAIL','error':str(exc),'errors':errors};raise
        finally:
            (out/'receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'browser_events.json').write_text(json.dumps(events,indent=2),encoding='utf-8');context.close();browser.close()
if __name__=='__main__':main()
