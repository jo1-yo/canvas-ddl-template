# canvas-ddl

**Get your Canvas deadlines emailed to you every morning.** Works with any
school's Canvas. No server, no app, nothing to install, free forever.

Canvas knows every due date but never warns you ahead of time. Its "Due Date"
notification only fires when an instructor *changes* a date, and the mobile
app's "Remind Me" has to be set one assignment at a time — which you can only
do for assignments you already know about. This closes that gap.

You get mail that looks like this:

> **📚 Your Canvas deadlines & exams — next 2 weeks**
>
> Hi!
>
> Here's your schoolwork from Canvas for the next two weeks.
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
> ## 📅 Coming Up Later
>
> **Oct 5**
>
> - English — [Essay](#)
> - Due at 11:59 PM
>
> ---
>
> 💡 **Quick Summary:** You have 2 assignments and 1 exam coming up in the next two weeks. Use [pawse](#) to manage your time more effectively.

Each title links straight to the assignment in Canvas. Exams are pulled into
their own section wherever they fall, because they need preparing for rather
than handing in.

---

## Setup

Takes about five minutes. You do not need to know how to code, and you will
never edit a file unless you want to.

### 1. Make your own copy

Click **[Use this template](../../generate)** → **Create a new repository**.

Name it anything. **Choose Private** — it is your class schedule, and private
repositories also avoid a GitHub rule that switches off scheduled jobs in public
repositories after 60 days of quiet.

> Prefer forking? That works too, but forks start with scheduled workflows
> switched off — see [Is it actually running?](#is-it-actually-running) below.

### 2. Get your Canvas calendar link

In Canvas: **Calendar** → scroll the right-hand sidebar to the bottom →
**Calendar Feed** → copy the link. It ends in `.ics`.

It looks like `https://canvas.yourschool.edu/feeds/calendars/user_AbCd1234....ics`

> **Treat this link like a password.** Anyone who has it can read your course
> calendar until you regenerate it. Do not paste it into a chat, an issue, or a
> file. It goes in one place only: the secret box in the next step.
>
> If it ever leaks, open that same Calendar Feed dialog and reset the link.

### 3. Give it to your repository

In **your** copy of the repo: **Settings** → **Secrets and variables** →
**Actions** → green **New repository secret** button.

- **Name:** `CANVAS_ICS_URL`
- **Secret:** the link from step 2

Click **Add secret**. That is the only secret you need.

### 4. Set your timezone

Same page, **Variables** tab → **New repository variable**.

- **Name:** `TIMEZONE`
- **Value:** your [IANA timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List) —
  `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Asia/Shanghai`, …

Skip this and it assumes `America/Los_Angeles`, which will put your deadlines on
the wrong day if you are not there.

### 5. Try it

**Actions** tab → **Canvas ddl** in the left sidebar → **Run workflow** button →
tick **dry_run** → green **Run workflow**.

Wait a minute, refresh, click into the run, open **Send digest**. You will see
your real deadlines printed in the log. Nothing was sent.

If that looks right, run it again with **dry_run** unticked. This time it opens
an issue in your repo and GitHub emails it to you.

**That's it.** From now on it runs by itself every morning at 08:00 in your
timezone. You do not open anything — you just get mail.

---

## Is it actually running?

Two GitHub behaviours switch scheduled jobs off silently. Check both once.

**If you forked instead of using the template**, scheduled workflows are
disabled by default. Go to **Actions**. If you see a banner offering to enable
workflows, click it. Then open **Canvas ddl** in the sidebar; if there is an
**Enable workflow** button, click that too.

**If you made your copy public**, GitHub disables the schedule after 60 days
with no commits. This repo pushes a dated marker every few weeks to prevent
that, but the simplest protection is to keep your copy **private**.

To confirm it is live: **Actions** → **Canvas ddl** → you should see runs
appearing each morning.

---

## Not getting the email?

Work down this list.

1. **Check the repo first.** Open the **Issues** tab. If today's digest is
   there, the tool works and the problem is mail delivery — keep reading. If it
   is not there, go to **Actions** and look for a failed run.
2. **Check which address GitHub uses.** <https://github.com/settings/emails>
   shows your addresses; <https://github.com/settings/notifications> has the
   **Default notification email** dropdown. That is where the mail goes.
3. **Check spam** for anything from `notifications@github.com`.
4. **Make sure you are assigned.** The digest is assigned to the repository
   owner, which is what triggers the mail. If you renamed your account, run it
   once more.
5. **Red X on a run?** Click it, open **Send digest**, and read the last line:

| Message | Fix |
|---|---|
| `CANVAS_ICS_URL is not set` | Step 3 — check the secret name is spelled exactly |
| `Canvas returned HTTP 404` | Your feed link changed. Get a fresh one and update the secret |
| `response is not an iCalendar feed` | The secret holds something other than the `.ics` link |
| `TIMEZONE ... is not a valid IANA timezone` | Step 4 — use a name from the list, e.g. `America/New_York` |
| `Delivery failed (issue): ... 403` | Actions lost write access. **Settings → Actions → General → Workflow permissions** → *Read and write* |

---

## Making it yours

Everything below is optional. All of it lives in **Settings → Secrets and
variables → Actions → Variables**, so you never touch code.

### Leave things out

Instructors often file class sessions as Canvas assignments, so nothing in the
feed tells "Lesson 4 Day 2: verbs" apart from "Problem Set 3". Only you know
which is which.

Add a variable named `IGNORE_TITLES`, one regular expression per line. Anything
whose title matches is left out:

```
^Lesson \d+ Day
^Reading for
office hours
```

Not sure about regular expressions? Plain words work — a line saying `quiz`
drops anything with "quiz" in the title. Matching ignores upper/lower case.

A line that is not valid gets reported in the log and skipped; the rest of the
digest still goes out.

### What counts as an exam

Nothing in a Canvas feed marks an exam, so the tool goes by the title. By
default anything matching `exam`, `midterm`, `final`, `quiz` or `test` moves
into the 📝 Exams section.

Add a variable named `EXAM_TITLES` to replace that with your own pattern:

```
\b(exam|midterm|final|prelim)\b
```

### How far ahead to look

Two more variables, if the defaults do not suit you:

- `WINDOW_DAYS` — how far ahead the email reaches. Default `14`.
- `SOON_DAYS` — where 🔴 Coming Up Soon stops and 📅 Coming Up Later
  starts, counting today as day one. Default `7`.

### What time it arrives

This one *is* a file: edit the `cron` line in
[`.github/workflows/notify.yml`](.github/workflows/notify.yml). GitHub only
speaks **UTC**, so convert from your own timezone.

| You want | cron |
|---|---|
| Every day 08:00 New York (default) | `0 12 * * *` |
| Every day 20:00 New York | `0 0 * * *` |
| Every day 08:00 Los Angeles | `0 15 * * *` |
| Mondays only, 08:00 New York | `0 12 * * 1` |

Daylight saving shifts these by an hour twice a year. For a deadline digest that
is fine. GitHub also runs scheduled jobs a few minutes late when it is busy.

### Phone push instead of email

Email needs nothing installed, so it is the default. For a real lock-screen
notification, iOS requires an app — this supports
[Bark](https://apps.apple.com/app/bark-customed-notifications/id1403753865):

1. Install Bark, open it, and copy **only the key** from your push URL: in
   `https://api.day.app/AbCdEf123456/...` the key is `AbCdEf123456`.
2. Add it as a secret named `BARK_KEY`.
3. Add a variable `CHANNEL` = `bark`.

Storing the whole URL instead of the key is the usual mistake; Bark answers that
with HTTP 400 and the tool tells you so.

### Show class meetings too

Add a variable `INCLUDE_EVENTS` = `1` to also list calendar entries that are not
submittable work, such as office hours.

---

## What it can't do

- **It does not know what you have already submitted.** The calendar feed
  carries due dates and nothing else, so finished work still shows up. Reading
  submission status would need a Canvas API token, which can read your grades
  and submit work as you — far too dangerous a credential for a reminder.
- **It cannot tell you when your feed link breaks.** If you regenerate the link
  in Canvas, update the `CANVAS_ICS_URL` secret, or runs will start failing in
  the Actions tab. GitHub emails you about failed scheduled runs.

## Why the calendar feed and not the Canvas API

The API needs a personal access token, and a Canvas token can read your grades,
read your private messages, and submit work as you. A third-party app cannot
even ask for one properly without your school's Canvas administrator creating a
developer key first.

The calendar feed needs no administrator, works at every school, is read-only,
and you can revoke it yourself by regenerating the link. The only thing it costs
is submission status.

## How it works

```
your Canvas .ics
      ↓  ics.py          download, parse, drop recurring class meetings,
      ↓                  rewrite calendar links into direct assignment links
      ↓  __main__.py     apply IGNORE_TITLES
      ↓  digest.py       select() sorts the next two weeks into Soon /
      ↓                  Exams / Later, then writes Markdown for the
      ↓                  email and plain text for a push
      ↓  github_issue.py open today's issue, close yesterday's
```

`ics.py` and `digest.py` touch neither the network nor any notification service,
which is why the tests live there.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests/ -q

export CANVAS_ICS_URL="https://canvas.yourschool.edu/feeds/calendars/user_xxx.ics"
export TIMEZONE="America/New_York"
.venv/bin/python -m canvas_ddl --dry-run
```

`--dry-run` prints the digest instead of sending it and needs no credentials
beyond the feed URL.

## License

MIT — see [LICENSE](LICENSE).
