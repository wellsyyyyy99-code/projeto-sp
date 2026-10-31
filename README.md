# Projeto SP 🇧🇷: 44 episodes to São Paulo

**Episode 1:** Sunday 1 November. **Episode 44:** Monday 14 December. **Flight:** 17 December.

## What the robot builds

**Every episode:**
- Listen twice
- Shadow each line (slow, then story speed)
- **Be George:** say his lines in the gaps
- **Your turn:** answer the characters' questions out loud
- A final listen

**Every pack:**
- A **Drills** episode for the gym
- A **🗣️ Speaking gym** episode: you get a topic, talk non-stop until the beep, then go again, faster
- An Anki deck, including "Answer aloud" cards

**Transcript pages:** as-heard spelling, hidden English, a speaking mission for each episode, and a ready-made AI voice prompt with a Copy button.

**Speed ladder:** the story gets faster as you go, from 25% slower than normal up to 12% faster by the end.

## Setup

1. Create a new repo called `projeto-sp`, set it to **Public**, and upload the **contents** of this folder.
2. **Add file → Create new file**, name it `.github/workflows/build.yml`, paste in `workflow-copy.yml`, and **Commit**.
3. **Settings → Pages → Source: GitHub Actions**.
4. **Actions → Build Projeto SP → Run workflow**. Wait for the ✅. The first run takes about 10 minutes.
5. Your site will be at `https://<username>.github.io/projeto-sp/`, and your podcast feed at `…/projeto-sp/feed.xml`.

## Every Sunday

Generate two packs in the Claude Project, in separate chats. The tracker's **Sundays** tab shows which numbers.

For each pack:

1. On GitHub, create `packs/pack-NN.json`, paste the reply, and commit.
2. Import the new deck into Anki and **Sync**.
3. Upload the JSON file to the Project.

## If something goes wrong

- **Red ❌:** usually an incomplete paste. Regenerate the pack and paste again.
- **Voice service hiccup:** press **Re-run jobs**.
- **Rebuild everything:** run the workflow manually with **force = 1**.
