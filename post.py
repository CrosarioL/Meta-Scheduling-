#!/usr/bin/env python3
"""HayatTime scheduled poster (runs on GitHub Actions).
Posts the next pending video in queue.json:
  Instagram reel (+ CTA comment) and one Facebook Page post.
The Meta token comes from the META_TOKEN repository secret. It is never stored in the repo."""
import datetime, json, os, subprocess, sys, time

G = 'https://graph.facebook.com/v24.0'
IG = '17841462699125665'
PAGE = '738913292646016'
HERE = os.path.dirname(os.path.abspath(__file__))
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
        i = next((k for k, q in enumerate(Q) if q['status'] == 'pending'), None)
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
    if todo('fb'):
        res['fb'] = fb_video(path, q['caption'])
    if todo('ig'):
        res['ig'] = ig_reel(path, q['caption'])
        if 'id' in res['ig'] and q.get('comment'):
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
