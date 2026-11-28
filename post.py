#!/usr/bin/env python3
"""Scheduled Instagram + Facebook poster (brand settings in brand.json) (runs on GitHub Actions).
Posts the next pending video in queue.json:
  Instagram reel (+ CTA comment), an Instagram trial reel (different caption) and one Facebook Page post.
The Meta token comes from the META_TOKEN repository secret. It is never stored in the repo."""
import datetime, json, os, subprocess, sys, time

G = 'https://graph.facebook.com/v24.0'
HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(HERE, 'brand.json')))
IG = BRAND['ig_user_id']
PAGE = BRAND['fb_page_id']
QF = os.path.join(HERE, 'queue.json')
VID = os.path.join(HERE, 'videos')
TOKEN = os.environ.get('META_TOKEN', '').strip()


def log(*a):
    print(datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S'), *a, flush=True)


def curl(args, timeout=900):
    r = subprocess.run(['curl', '-sS'] + args, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {'raw': r.stdout[:300], 'err': r.stderr[:300]}


def get(path, token=None):
    return curl(['-G', f'{G}/{path}', '--data-urlencode', f'access_token={token or TOKEN}'])


def post(path, fields, token=None):
    a = ['-X', 'POST', f'{G}/{path}', '--data-urlencode', f'access_token={token or TOKEN}']
    for k, v in fields.items():
        a += ['--data-urlencode', f'{k}={v}']
    return curl(a)


def alt_caption(c):
    """Slightly different caption for the 2nd Facebook post."""
    lines = c.split('\n')
    tags = [l for l in lines if l.strip().startswith('#')]
    body = '\n'.join(l for l in lines if not l.strip().startswith('#')).rstrip()
    new = body
    for a, b in [("Comment APP and I'll DM you", "Comment “APP” \U0001F447 and I'll send you"),
                 ("Comment APP and I’ll DM you", "Comment “APP” \U0001F447 and I’ll send you")]:
        if a in new:
            new = new.replace(a, b, 1)
            break
    first, _, rest = new.partition('\n')
    new = first.rstrip() + ' \U0001F90D' + ('\n' + rest if rest else '')
    tags = [' '.join(reversed(t.split())) for t in tags]
    return new + ('\n\n' + '\n'.join(tags) if tags else '')


def ig_reel(path, caption):
    size = os.path.getsize(path)
    for attempt in range(3):
        c = post(f'{IG}/media', {'media_type': 'REELS', 'upload_type': 'resumable', 'caption': caption})
        if 'id' not in c:
            return {'error': c}
        cid = c['id']
        uri = c.get('uri') or f'https://rupload.facebook.com/ig-api-upload/v24.0/{cid}'
        up = curl(['-X', 'POST', uri, '-H', f'Authorization: OAuth {TOKEN}', '-H', 'offset: 0',
                   '-H', f'file_size: {size}', '--data-binary', f'@{path}'])
        log('instagram upload try', attempt + 1, 'ok' if up.get('success') else str(up)[:150])
        st = {}
        for _ in range(40 if up.get('success') else 4):
            time.sleep(30)
            st = get(f'{cid}?fields=status_code,status')
            if st.get('status_code') in ('FINISHED', 'ERROR', 'EXPIRED'):
                break
        log('instagram processing', st.get('status_code'), str(st.get('status', ''))[:120])
        if st.get('status_code') == 'FINISHED':
            p = post(f'{IG}/media_publish', {'creation_id': cid})
            if 'id' not in p:
                return {'error': p}
            info = get(f"{p['id']}?fields=permalink")
            log('LIVE instagram', info.get('permalink'))
            return {'id': p['id'], 'permalink': info.get('permalink')}
    return {'error': 'instagram upload did not finish after 3 tries'}


RAW = f"https://raw.githubusercontent.com/{os.environ.get('GITHUB_REPOSITORY', 'CrosarioL/Meta-Scheduling-')}/main/videos/"


def ig_trial(fname, caption):
    """Instagram trial reel: shown to non-followers only, never on the profile grid.
    Instagram fetches the file itself from the public repo link (trials only work that way).
    If Instagram still puts it on the grid, it is deleted straight away."""
    url = RAW + fname
    code = subprocess.run(['curl', '-sI', '-o', '/dev/null', '-w', '%{http_code}', url],
                          capture_output=True, text=True).stdout
    if code != '200':
        return {'error': f'trial skipped: video link not public (HTTP {code}); the repo must be public'}
    c = post(f'{IG}/media', {'media_type': 'REELS', 'video_url': url, 'caption': caption,
                            'trial_params': '{"graduation_strategy":"MANUAL"}', 'share_to_feed': 'false'})
    if 'id' not in c:
        return {'error': c}
    st = {}
    for _ in range(40):
        time.sleep(30)
        st = get(f"{c['id']}?fields=status_code,status")
        if st.get('status_code') in ('FINISHED', 'ERROR', 'EXPIRED'):
            break
    if st.get('status_code') != 'FINISHED':
        return {'error': f"trial processing {st.get('status_code')} {str(st.get('status', ''))[:120]}"}
    p = post(f'{IG}/media_publish', {'creation_id': c['id']})
    if 'id' not in p:
        return {'error': p}
    info = get(f"{p['id']}?fields=permalink,is_shared_to_feed")
    if info.get('is_shared_to_feed') is not False:
        curl(['-X', 'DELETE', f"{G}/{p['id']}", '--data-urlencode', f'access_token={TOKEN}'])
        log('trial came out as a normal grid reel, deleted it', info)
        return {'error': 'trial was not a real trial (showed on grid); deleted'}
    log('LIVE instagram trial', info.get('permalink'))
    return {'id': p['id'], 'permalink': info.get('permalink')}


def fb_video(path, caption):
    pt = get(f'{PAGE}?fields=access_token').get('access_token')
    if not pt:
        return {'error': 'no page token'}
    r = curl(['-X', 'POST', f'{G}/{PAGE}/videos', '-F', f'access_token={pt}', '-F', f'source=@{path}',
              '--form-string', f'description={caption}'], timeout=1500)
    if 'id' not in r:
        return {'error': r}
    log('LIVE facebook', r['id'])
    return {'id': r['id'], 'permalink': f"https://www.facebook.com/reel/{r['id']}/"}


def main():
    if not TOKEN:
        print('META_TOKEN secret is missing')
        sys.exit(1)
    me = get(f'{IG}?fields=username')
    if 'username' not in me:
        print('TOKEN PROBLEM, nothing posted:', json.dumps(me)[:300])
        sys.exit(1)
    Q = json.load(open(QF))
    force = '--now' in sys.argv
    last = max([q.get('posted_at', '') for q in Q if q.get('posted_at')] or [''])
    if last and not force:
        dt = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.datetime.fromisoformat(last.rstrip('Z'))
        if dt.total_seconds() < 50 * 60:
            print('SKIP: posted', int(dt.total_seconds() // 60), 'min ago')
            return
    # finish a half-posted video first, otherwise take the next pending one
    i = next((k for k, q in enumerate(Q) if q['status'] == 'partial' and q.get('retries', 0) < 2), None)
    if i is None:
        # newest curated batch first (higher priority), otherwise queue order
        pend = [k for k, q in enumerate(Q) if q['status'] == 'pending']
        i = max(pend, key=lambda k: (Q[k].get('priority', 0), -k)) if pend else None
    if i is None:
        print('QUEUE EMPTY')
        return
    q = Q[i]
    path = os.path.join(VID, q['file'])
    if not os.path.exists(path):
        print('MISSING FILE', q['file'])
        sys.exit(1)
    log('posting', q['file'])
    res = q.setdefault('results', {})
    todo = lambda k: k not in res or 'error' in res[k]
    if not BRAND.get('facebook', True):
        res['fb'] = {'id': 'off'}
    if todo('fb'):
        res['fb'] = fb_video(path, q['caption'])
    if todo('ig'):
        res['ig'] = ig_reel(path, q['caption'])
        ig_live_at = time.time()
    if BRAND.get('trials', True) and todo('trial') and 'id' in res.get('ig', {}) and res.get('trial', {}).get('tries', 0) < 2:
        tries = res.get('trial', {}).get('tries', 0) + 1
        res['trial'] = ig_trial(q['file'], alt_caption(q['caption']))
        res['trial']['tries'] = tries
    # CTA comment goes up about 15 minutes after the reel, not the instant it publishes
    if 'id' in res.get('ig', {}) and q.get('comment') and 'ig_comment' not in res:
        wait = 15 * 60 - (time.time() - locals().get('ig_live_at', 0))
        if wait > 0:
            log('waiting', int(wait // 60), 'min before the CTA comment')
            time.sleep(wait)
        res['ig_comment'] = post(f"{res['ig']['id']}/comments", {'message': q['comment']})
    ok = all('id' in res.get(k, {}) for k in ('ig', 'fb'))
    if q['status'] == 'partial':
        q['retries'] = q.get('retries', 0) + 1
    q['status'] = 'posted' if ok else 'partial'
    q['posted_at'] = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds') + 'Z'
    json.dump(Q, open(QF, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'file': q['file'], 'status': q['status'],
                      'links': {k: v.get('permalink') for k, v in res.items() if isinstance(v, dict) and v.get('permalink')}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
