#!/usr/bin/env python3
"""Queue a new batch of videos (normally one idea in 3 versions).
Usage: python3 add_videos.py batch.json
batch.json = [{"file": "/path/to/video.mp4", "caption": "...", "comment": "..."}, ...]
- Copies each video into videos/ and adds it to queue.json ahead of older videos.
- Refuses exact duplicates (same file contents already queued or posted)."""
import hashlib, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QF = os.path.join(HERE, 'queue.json')
VID = os.path.join(HERE, 'videos')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

Q = json.load(open(QF))
known = {}
for q in Q:
    p = os.path.join(VID, q['file'])
    h = q.get('sha256') or (sha(p) if os.path.exists(p) else None)
    if h:
        known[h] = q['file']
batch = json.load(open(sys.argv[1]))
prio = max([q.get('priority', 0) for q in Q] + [0]) + 1
captions = set()
for b in batch:
    src = b['file']
    if os.path.getsize(src) > 95e6:
        sys.exit(f'{src} is over 95 MB; compress it first')
    h = sha(src)
    if h in known:
        sys.exit(f'DUPLICATE: {src} is the same file as {known[h]}; make a real variation (hook, pixels, CTA)')
    if b['caption'] in captions:
        sys.exit('DUPLICATE CAPTION inside this batch; give each version its own caption')
    captions.add(b['caption'])
    name = os.path.basename(src)
    if os.path.exists(os.path.join(VID, name)):
        sys.exit(f'videos/{name} already exists; rename the file')
    shutil.copy(src, os.path.join(VID, name))
    Q.append({'file': name, 'caption': b['caption'], 'comment': b.get('comment', ''),
              'status': 'pending', 'priority': prio, 'sha256': h})
    known[h] = name
    print('queued', name)
json.dump(Q, open(QF, 'w'), ensure_ascii=False, indent=1)
print('Done. Commit and push: git add videos queue.json && git commit -m "Queue new batch" && git push')
