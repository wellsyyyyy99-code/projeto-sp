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

## 🥊 Treino: the speaking half

**Treino** is the phone app for speaking: https://claude.ai/artifact/4eS5Vh7pkT5wanWQAeNbB5

One session a day, about 20 minutes, three rounds:

1. **Drills.** Your own mistakes and the phrases from the episodes, spoken. Each one comes back after 1, 2, 4, 7 and 12 days. Three correct days beats a mistake.
2. **Conversa.** A role-play of one of the 15 situations you have to win in Brazil (`curriculum/situations.json`). A win is every goal done in Portuguese and 7/10 or more. Then win it again with a twist.
3. **Ouvido.** Ten lines from the episodes, no text, at rising speed.

On Sundays there is a five-question oral exam, scored the same way every week.

Voice: every line has recorded audio. To answer, speak into your phone keyboard's mic (add the Portuguese (Brasil) keyboard) or type; accents don't matter. In Chrome on a computer or Android the app also has its own tap-to-talk mic.

## Every day and every Sunday: nothing to do

Three scheduled agents run the machine (`agents/README.md` explains all of it):

- **Coach** (daily, 05:40): reads yesterday's results, updates the tracker sheet, writes new drills for the rule you keep breaking, sets today's scene.
- **Producer** (Sunday, 06:10): writes the week's two packs around your mistakes and pushes them here. The robot builds the audio, decks and transcripts.
- **Examiner** (Sunday, 07:20): sets the Sunday exam and sends the weekly numbers.

The only manual step left is optional: import the week's Anki deck from the home page.

## ⭐ Extras

Claude can add bonus audio as `packs/extras-*.json` (your corrected answers, Rafa's messages). The robot turns each one into an MP3 in the podcast feed and a ⭐ Extras list on the home page.

## If something goes wrong

- **Red ❌:** usually an incomplete paste. Regenerate the pack and paste again.
- **Voice service hiccup:** press **Re-run jobs**.
- **Rebuild everything:** run the workflow manually with **force = 1**.
