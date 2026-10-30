#!/usr/bin/env python3
"""Run inside an isolated ZAP container; evaluate only after the spider stops.

ZAP history also contains status-zero discovery placeholders. They are not
counted as HTTP responses or asserted to have reached the target.
"""
import json,time,urllib.parse,urllib.request,sys,re
mode=sys.argv[1]; limit=float(sys.argv[2]); target='http://crawlmaze:3460/'
base='http://127.0.0.1:8090/JSON/'
def call(path,**kw):
    with urllib.request.urlopen(base+path+'/?'+urllib.parse.urlencode(kw),timeout=15) as r:
        p=json.load(r)
    if 'code' in p: raise RuntimeError((path,p))
    return p
call('core/action/newSession',name='',overwrite='true')
call('context/action/newContext',contextName='local-maze')
call('context/action/includeInContext',contextName='local-maze',regex=r'http://crawlmaze:3460/.*')
call('context/action/setContextInScope',contextName='local-maze',booleanInScope='true')
for name,value in [('setOptionPostForm','false'),('setOptionParseRobotsTxt','false'),('setOptionParseSitemapXml','false')]:
    call('spider/action/'+name,Boolean=value)
call('spider/action/setOptionThreadCount',Integer='1')
started=time.monotonic(); phases=[]
def run_traditional(end):
    s=call('spider/action/scan',url=target,contextName='local-maze',subtreeOnly='true'); sid=s['scan']
    done=False
    while time.monotonic()<end:
        status=int(call('spider/view/status',scanId=sid)['status'])
        if status>=100: done=True; break
        time.sleep(1)
    if not done: call('spider/action/stop',scanId=sid)
    found=call('spider/view/results',scanId=sid).get('results',[])
    phases.append({'engine':'traditional','completed':done,'elapsed_seconds':round(time.monotonic()-started,3),'candidate_count':len(set(found))})
def run_client(end):
    s=call('clientSpider/action/scan',browser='firefox-headless',url=target,contextName='local-maze',numberOfBrowsers='1',scopeCheck='STRICT'); sid=s['scan']
    done=False
    while time.monotonic()<end:
        status=int(call('clientSpider/view/status',scanId=sid)['status'])
        if status>=100: done=True; break
        time.sleep(1)
    if not done: call('clientSpider/action/stop',scanId=sid)
    call('client/action/exportClientMap',pathYaml='/tmp/engramsec-'+mode+'-map.yaml')
    phases.append({'engine':'client','completed':done,'elapsed_seconds':round(time.monotonic()-started,3)})
end=started+limit
if mode in ('traditional','combined'): run_traditional(end)
if mode in ('client','combined') and time.monotonic()<end: run_client(end)
elapsed=time.monotonic()-started
messages=call('core/view/messages',start=0,count=10000).get('messages',[])
records=[]
for m in messages:
    request=m.get('requestHeader',''); response=m.get('responseHeader','')
    first=request.splitlines()[0] if request else ''; parts=first.split()
    if len(parts)<2: continue
    url=urllib.parse.urljoin(target,parts[1]); parsed=urllib.parse.urlsplit(url)
    if parsed.hostname!='crawlmaze' or parsed.port!=3460: continue
    status=re.search(r'^HTTP/\S+\s+(\d+)',response)
    records.append({'method':parts[0],'path':urllib.parse.unquote(parsed.path or '/'),'parameter_names':sorted({k for k,v in urllib.parse.parse_qsl(parsed.query,keep_blank_values=True)}),'status':int(status.group(1)) if status else None})
# The evaluator is contacted directly only after the spider has stopped.
categories=['css','headers','html','javascript','misc']; expected={}
for c in categories:
    with urllib.request.urlopen(target+'fetch-expected-results?'+urllib.parse.urlencode({'path':c}),timeout=5) as r: vals=json.load(r)
    expected[c]={urllib.parse.unquote(urllib.parse.urlsplit(x).path or '/') for x in vals}
paths={r['path'] for r in records if r['status'] is not None and 200<=r['status']<300}
bycat={c:{'expected':len(v),'fetched':len(v & paths)} for c,v in expected.items()}
summary={'mode':mode,'budget_seconds':limit,'elapsed_seconds':round(elapsed,3),'phases':phases,'history_entries':len(records),'response_bearing_messages':sum(r['status'] is not None and r['status']>=100 for r in records),'status_zero_or_missing':sum(r['status'] is None or r['status']==0 for r in records),'unique_successful_paths':len(paths),'methods_in_history':{m:sum(r['method']==m for r in records) for m in sorted({r['method'] for r in records})},'expected_total':sum(len(v) for v in expected.values()),'expected_fetched':sum(len(v & paths) for v in expected.values()),'categories':bycat}
open('/tmp/engramsec-'+mode+'-summary.json','w').write(json.dumps(summary,indent=2))
open('/tmp/engramsec-'+mode+'-records.json','w').write(json.dumps(records))
print(json.dumps(summary))
