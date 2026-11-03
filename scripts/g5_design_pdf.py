"""Render employer design note as a genuinely page-checked 2-page PDF.

Reads the unchanged Markdown source; prints to A4 using local Chromium and
validates the resulting PDF page count with pypdf.
"""
from pathlib import Path
from html import escape
import re,json,hashlib
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'docs/submission/ARCHITECTURE_DESIGN_NOTE.md'
dest=ROOT/'docs/submission/ARCHITECTURE_DESIGN_NOTE.pdf'
text=source.read_text(encoding='utf-8')
def inline(v):
    v=escape(v)
    v=re.sub(r'`([^`]+)`',r'<code>\1</code>',v)
    v=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',v)
    return v
parts=[]; items=[]
def flush():
    if items:
        parts.append('<ul>'+''.join('<li>'+inline(x)+'</li>' for x in items)+'</ul>')
        items.clear()
for line in text.splitlines():
    line=line.strip()
    if line.startswith('# '):
        flush();parts.append('<h1>'+inline(line[2:])+'</h1>')
    elif line.startswith('## '):
        flush();parts.append('<h2>'+inline(line[3:])+'</h2>')
    elif line.startswith('- '):
        items.append(line[2:])
    elif not line:
        flush()
    else:
        flush();parts.append('<p>'+inline(line)+'</p>')
flush()
css="""@page{size:A4;margin:16mm 17mm 16mm 17mm}
html,body{margin:0;padding:0;font-family:Arial,'Segoe UI',sans-serif;color:#1d2928;background:white}
h1{font-size:20px;line-height:1.28;margin:0 0 11px;padding:0 0 9px;border-bottom:2px solid #e85b28;color:#20362a;break-after:avoid}
h2{font-size:14.2px;line-height:1.32;margin:15px 0 7px;color:#2e4a3d;break-after:avoid}
p,li{font-size:12.15px;line-height:1.45;margin:0 0 9px}
p{orphans:3;widows:3}
ul{margin:2px 0 8px;padding-left:16px}
li{margin-bottom:3px}
strong{font-weight:700;color:#1d3129}
code{font-family:Consolas,'Courier New',monospace;font-size:10.7px;overflow-wrap:anywhere}
"""
html='<html><head><meta charset="UTF-8"><style>'+css+'</style></head><body>'+''.join(parts)+'</body></html>'
with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    page=browser.new_page()
    page.set_content(html,wait_until='load')
    page.pdf(path=str(dest),format='A4',print_background=True,prefer_css_page_size=True)
    browser.close()
pdf=PdfReader(str(dest)); pages=len(pdf.pages)
report={'status':'PASS' if pages<=2 else 'FAIL','pages':pages,
        'source_markdown_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'pdf_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'pdf_bytes':dest.stat().st_size}
receipt=ROOT/'artifacts/receipts/g5_design_page_proof_20261103.json'
receipt.parent.mkdir(parents=True,exist_ok=True)
receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
if pages>2:raise SystemExit('Design note over employer two-page limit')
