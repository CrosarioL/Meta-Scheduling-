# Auto-poster (Instagram + Facebook)

Posts one video 3 times a day (11:47, 16:47, 20:47 UK winter time). Each video goes out as: an Instagram reel with a CTA comment, an Instagram trial reel (non-followers only, different caption) and one Facebook Page post.

- `brand.json`: which Instagram account and Facebook Page to post to, and whether trials / Facebook are on.
- `queue.json`: the posting order. New batches added with `add_videos.py` go ahead of older videos. The bot marks each one `posted`.
- `videos/`: the video files. The repo must be public so Instagram can fetch trial videos; the token stays private in Secrets.
- `post.py`: the poster. `.github/workflows/post.yml`: the schedule.

**Setup:** add the Meta access token as a repository secret named `META_TOKEN` (Settings, Secrets and variables, Actions). If posts fail with "TOKEN PROBLEM", replace it.

**Post one right now:** Actions tab, "Post next HayatTime video", Run workflow, tick "now".

**Add videos:** see `CLAUDE.md` (`python3 add_videos.py batch.json`, then commit and push).
