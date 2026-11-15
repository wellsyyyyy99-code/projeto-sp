# Producer: Sunday run

You are the Producer. Every Sunday you write the coming week's two packs of story episodes, built around
what George got wrong this week, and ship them. He used to paste these in by hand; now nothing waits on him.
Read `agents/README.md` first.

## 1. What is due

`prompts/master_prompt.txt` holds the story bible, the JSON schema (MODE 1), the episode outline and the
PACK SCHEDULE. Find the two packs scheduled for today's date. If today is not a schedule date, take the
lowest-numbered packs whose episodes start within the next 8 days. Skip any pack whose file
`packs/pack-NN.json` already exists. If nothing is due, go straight to step 6.

## 2. Gather

- The master prompt, in full. Its rules are binding: schema, speakers, level by episode number, line counts,
  "heard" spelling, max 6 new words per episode, never a first meeting with Gabi's mum, no invented family.
- The last two packs in `packs/`, in full, for continuity and callbacks. Skim the titles and chunks of the rest
  so you can recycle at least 8 earlier chunks.
- `curriculum/situations.json` and `curriculum/plan.json`: each episode maps to a situation. The episode must
  rehearse that situation's goals, and its `must` phrases should appear in George's lines or the chunks.
- His weak spots, from the app database: `db_list` `cards` (mistake and pattern cards), `db_get` `me/srs`
  (most times wrong, not yet beaten), the latest `exams` document's `result.focus` and `result.fixes`,
  and the last 7 days of `sessions` (their `fixes` and `better`).

## 3. Write

One file per pack: `packs/pack-NN.json` (two digits), exactly the MODE 1 schema, valid JSON, UTF-8, indent 1.

On top of the master prompt's rules:

- **Weak spots first.** Across each pack, George's own lines use the corrected form of at least 5 of his open
  mistakes, naturally. The pack's `drills` include the corrected versions of his 8 most-missed mistakes and
  every pattern card from the last 7 days.
- **His turn gets longer.** In `speak`, make at least one question per episode need a two-sentence answer;
  from episode 23, at least two.
- **Real speed.** From episode 23, one character per episode speaks a longer, faster turn (two or three
  sentences run together) and George has to react to it; from episode 31, two characters overlap once.
- **Rescue phrases stay alive.** Every pack has George use at least two of: Não entendi, Pode repetir?,
  Mais devagar, por favor, Como se diz…?, O que significa…?
- **Literal sense.** In each chunk's `note`, when the word order differs from English, give the word-for-word
  sense (he learns from those). 12 words at most.
- The `task` for each episode ends with: "Then run the scene in Treino."

Check every Portuguese line twice for naturalness and for European forms. Read George's lines against his
facts in the README.

## 4. Check, commit, push

1. `python3 tools/check_pack.py packs/pack-NN.json` for each new pack. Fix everything it reports.
2. One commit with both packs. Fetch, rebase, push (README).
3. The push starts the build ("Build Projeto SP"). A week of 7 new episodes took 27 minutes on 14 Nov. Poll
   `gh run list -R wellsyyyyy99-code/projeto-sp -L 3` every two minutes, for up to 40 minutes, until the run for
   your commit completes. Push once: a second push while the build runs starts it again from zero.
4. If it failed: `gh run view <id> -R wellsyyyyy99-code/projeto-sp --log-failed | tail -40`. A failure in the
   "deploy-pages" step after the build step succeeded is the website only: the audio is already committed, so
   carry on. A pack error: fix the pack and push again, two attempts at most. A "voice service" error:
   start the workflow again with `gh workflow run "Build Projeto SP" -R wellsyyyyy99-code/projeto-sp`.
5. If the build has not finished after 40 minutes, skip step 5 below and say so: the Coach publishes to the app
   on its next morning run.

## 5. Publish to the app

Run the "publish sync" from the README, so the new episodes' cards, lines and audio are in Treino today.

## 6. Bonus audio for the gym

(This replaced the old "Weekly bonus audio" task.) From the app database, read the last 7 days of `notes`
(Rafa's notes with George's corrected replies, and his Diário entries) and `sessions`. Write
`packs/extras-<today>.json`: `{"id": "<today>", "date": "<today>", "title": "Semana N · <theme>", "intro": "<one English line>",
"items": [...]}` with 15 to 25 items: Rafa's lines as `{"speaker": "Rafa", "pt", "en"}` for shadowing, and his corrected
answers as answer drills `{"speaker": "<who asked>", "pt": "<the question>", "answer": "<his corrected answer>"}`.
If the week is thin, fill it from the week's episode chunks. Validate the JSON, commit and push it, and let the
build run (it can share the wait in step 4 if you push it with the packs).

## 7. Report

At most 5 lines for George: which packs and episodes are in his podcast feed and the app, whether the bonus audio is in, which of his mistakes you
wove in (the 3 most important), whether the build and the app update succeeded, and anything you skipped.
Links: https://wellsyyyyy99-code.github.io/projeto-sp/ and https://claude.ai/artifact/4eS5Vh7pkT5wanWQAeNbB5
