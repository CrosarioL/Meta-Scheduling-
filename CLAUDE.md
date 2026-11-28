# Posting system (read before touching anything)

This repo posts videos automatically: GitHub Actions runs `post.py` at 11:47, 16:47 and 20:47 (UTC). Each run posts ONE video from `queue.json`:
1. Instagram reel (the CTA comment is added about 15 minutes later)
2. Instagram trial reel (same video, slightly different caption, non-followers only; deleted automatically if Instagram puts it on the grid)
3. ONE Facebook Page post (never two)

Brand settings live in `brand.json`. The Meta token is the `META_TOKEN` repository secret; never put a token in any file or commit.

## Queuing a new batch (one idea, 3 versions)
1. Write `batch.json`: `[{"file": "/abs/path/v1.mp4", "caption": "...", "comment": "Comment APP ..."}, ...]`
2. `python3 add_videos.py batch.json`. It copies the files into `videos/`, puts them ahead of older videos, and refuses exact duplicate files or repeated captions.
3. `git add videos queue.json && git commit -m "Queue <idea name>" && git push`

## Rules
- Every version must be a real variation (different hook, pixels, CTA or body), never the same file re-uploaded.
- Do not add a second Facebook post, and do not post anything by hand with the API; let the schedule do it.
- Do not change the trial logic in `post.py` (trials use the public video link; the repo must stay public for that).
- Videos must be under 95 MB.
