# HayatTime scheduler

Posts one video 5 times a day (08:47, 11:47, 14:47, 17:47, 20:47 UK winter time) to the hayattime.app Instagram and the Hayat Time App Facebook Page (1 post).

- `queue.json`: the posting order. Each entry has the video file, caption and CTA comment. The bot marks each one `posted` and saves it back here.
- `videos/`: the video files.
- `post.py`: the poster. `.github/workflows/post.yml`: the schedule.

**Setup:** add the Meta access token as a repository secret named `META_TOKEN` (Settings, Secrets and variables, Actions). It expires every 60 days, so replace it when posts start failing with "TOKEN PROBLEM".

**Post one right now:** Actions tab, "Post next HayatTime video", Run workflow, tick "now".

**Add videos:** put the file in `videos/` and add an entry to `queue.json` with `"status": "pending"`.
