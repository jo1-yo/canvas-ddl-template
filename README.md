# canvas-ddl

**Your Canvas deadlines and exams, emailed to you every morning.** Works with
any school's Canvas. No server, no app, nothing to install, free.

Canvas knows every due date but never warns you ahead of time — its "Due Date"
notification only fires when an instructor *changes* a date. This closes that
gap.

> **📚 Your Canvas deadlines & exams — next 2 weeks**
>
> ## 🔴 Coming Up Soon
>
> **Sep 26**
>
> - Math 101 — [Problem Set 3](#)
> - Due at 11:59 PM
>
> ## 📝 Exams
>
> **Sep 30**
>
> - CS 201 — [Midterm](#)
> - 10:00 AM
>
> ---
>
> 💡 **Quick Summary:** You have 1 assignment and 1 exam coming up in the next two weeks.

Titles link straight to the assignment. Exams get their own section wherever
they fall.

---

## Setup

### 1. Get your Canvas calendar link

Canvas → **Calendar** → scroll the right sidebar to the bottom → **Calendar
Feed** → copy the link. It ends in `.ics`.

> ⚠️ **This link is a password.** Anyone holding it can read your course
> calendar. Never paste it into a chat, an issue, or a file — only into the
> secret box below. If it leaks, reopen that dialog and reset it.

### 2. Then either…

<table>
<tr><th>In the browser</th><th>In a terminal</th></tr>
<tr valign="top"><td>

1. **[Use this template](../../generate)** → **Create a new repository** →
   pick **Private**
2. In your new repo: **Settings → Secrets and variables → Actions**
3. **New repository secret** → name `CANVAS_ICS_URL`, value = your link
4. **Variables** tab → **New repository variable** → name `TIMEZONE`, value
   e.g. `America/New_York`

</td><td>

Needs the [GitHub CLI](https://cli.github.com) (`brew install gh && gh auth login`).

```bash
gh repo create my-canvas-ddl \
  --template jo1-yo/canvas-ddl-template \
  --private --clone
cd my-canvas-ddl
gh secret set CANVAS_ICS_URL
gh variable set TIMEZONE --body "America/New_York"
```

`gh secret set` prompts for the link without echoing it.

</td></tr>
</table>

Pick your timezone from the [IANA list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).
Skip it and you get `America/Los_Angeles`.

### 3. Check it works

**Actions → Canvas ddl → Run workflow**, tick **dry_run**, run it. The log
prints your real deadlines and sends nothing. Looks right? Run it again with
**dry_run** off — that one opens an issue and GitHub emails it to you.

```bash
gh workflow run notify.yml -f dry_run=true   # same thing from the terminal
```

**Done.** It runs by itself every morning at 08:00 in your timezone.

---

## Options

All optional. **Settings → Secrets and variables → Actions → Variables**, or
`gh variable set NAME --body "value"`.

| Variable | What it does | Default |
|---|---|---|
| `TIMEZONE` | Your IANA timezone | `America/Los_Angeles` |
| `IGNORE_TITLES` | One pattern per line; matching titles are left out | empty |
| `EXAM_TITLES` | What counts as an exam | `exam`, `midterm`, `final`, `quiz`, `test` |
| `WINDOW_DAYS` | How far ahead to look | `14` |
| `SOON_DAYS` | Where 🔴 Soon ends and 📅 Later begins | `7` |
| `INCLUDE_EVENTS` | `1` also lists class meetings and office hours | off |
| `CHANNEL` | `bark` sends an iPhone push instead of email | `issue` |

**`IGNORE_TITLES` is the one you'll want.** Instructors often file class
sessions as assignments, and nothing in the feed tells them apart from real
work. Plain words are fine — a line saying `quiz` drops anything with "quiz" in
the title. Case is ignored.

```
^Lesson \d+ Day
office hours
```

**When it arrives** is the only setting that lives in a file: the `cron` line in
[`.github/workflows/notify.yml`](.github/workflows/notify.yml). GitHub only
speaks UTC.

| You want | cron |
|---|---|
| 08:00 New York (default) | `0 12 * * *` |
| 20:00 New York | `0 0 * * *` |
| 08:00 Los Angeles | `0 15 * * *` |
| Mondays only, 08:00 New York | `0 12 * * 1` |

**For an iPhone push**, install [Bark](https://apps.apple.com/app/bark-customed-notifications/id1403753865),
copy **only the key** from your push URL (`https://api.day.app/AbCdEf123456/` →
`AbCdEf123456`), save it as a secret named `BARK_KEY`, and set `CHANNEL` to
`bark`.

---

## Troubleshooting

**Check the Issues tab first.** Today's digest there means the tool works and
only the email is missing — check
[your notification address](https://github.com/settings/notifications) and your
spam folder. Nothing there means a failed run; open **Actions** and read the
last line of **Send digest**:

| Message | Fix |
|---|---|
| `CANVAS_ICS_URL is not set` | Check the secret name is spelled exactly |
| `Canvas returned HTTP 404` | Your feed link changed — get a fresh one and update the secret |
| `response is not an iCalendar feed` | The secret holds something other than the `.ics` link |
| `TIMEZONE ... is not a valid IANA timezone` | Use a name from the IANA list |
| `Delivery failed (issue): ... 403` | **Settings → Actions → General → Workflow permissions** → *Read and write* |

**No runs at all?** Two GitHub behaviours switch schedules off silently. If you
**forked** instead of using the template, scheduled workflows start disabled —
go to **Actions** and click the enable buttons. If your copy is **public**,
GitHub disables the schedule after 60 days without a commit; this repo pushes a
dated marker to prevent that, but keeping your copy private avoids the rule
entirely.

---

## What it can't do

**It doesn't know what you've already submitted**, so finished work still shows
up. The calendar feed carries due dates and nothing else. Reading submission
status would need a Canvas API token — a credential that can read your grades
and submit work as you, and that a third-party tool can't even request without
your school's Canvas admin creating a developer key first. The feed needs no
admin, works everywhere, is read-only, and you can revoke it yourself.

**It can't tell you when your feed link breaks.** If you regenerate it in
Canvas, update the secret, or runs will start failing quietly in the Actions
tab.

## How it works

```
your Canvas .ics
  → ics.py           download, parse, drop recurring class meetings,
                     turn calendar links into direct assignment links
  → __main__.py      apply IGNORE_TITLES
  → digest.py        sort the next two weeks into Soon / Exams / Later,
                     write Markdown for email and plain text for push
  → github_issue.py  open today's issue, close yesterday's
```

`ics.py` and `digest.py` touch neither the network nor any notification
service, which is why the tests live there: `pytest tests/ -q`.

## License

MIT — see [LICENSE](LICENSE).
