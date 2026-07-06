# User Guide

A practical guide to using the AI Interview Simulator — no technical background needed.

## What this is

A place to practice real interviews — technical, behavioral, or HR — with an AI interviewer that
actually reacts to what you say. It's not a quiz with fixed questions: it asks follow-ups, adjusts
based on your answers, and gives you a real closing report with a score, strengths, gaps, and
concrete advice for next time.

## Getting Started

### Option 1 — Try it without an account
Click **"Try one interview without signing up"** on the login page. You'll be dropped straight into
setting up an interview — no email, no password. This gives you exactly one free interview so you can
see how it works before committing to an account. Note: because this doesn't create a real account,
if you close your browser or clear your browsing data, there's no way to get back into that session
or its report — sign up if you want your history to stick around.

### Option 2 — Create an account
Sign up with an email *and* phone number plus a password, or use "Continue with Google" /
"Continue with GitHub" for one-click sign-in. Signed-up accounts get 2 free interviews using the
app's built-in AI key before you'd need to add your own (see **Bring Your Own Key** below), and your
full session history and reports are saved permanently.

## Starting an Interview

1. From the dashboard, click **New Interview**.
2. Pick a type: **Technical** (DSA, system design, language/framework depth), **Behavioral**
   (STAR-format situational questions), or **HR** (culture fit, motivation, communication).
3. *Optional*: paste or upload a job description (PDF). The interviewer will tailor questions to that
   specific role, and the app will research a realistic interview length for that role/company if it
   can find real information about it online.
4. *Optional*: upload your résumé (PDF). The interviewer can then ask about your actual listed
   projects and experience, not just generic questions.
5. Choose which AI model to use — the app default (no setup needed) or your own key if you've added
   one (see below).
6. Click **Start interview**.

## During the Interview

- The interviewer's question streams in live, like a real chat.
- Type your answer and send it — the next question follows, informed by what you just said.
- A timer in the top corner shows elapsed time against the interview's target length. This target
  isn't a hard cutoff — a strong candidate might run a bit longer, a short but conclusive interview
  ending early is also fine. The interview always ends with a real closing statement from the
  interviewer, never an abrupt stop.
- **Terminate**: if you need to stop early for any reason, click **Terminate** in the top corner.
  You'll be asked to confirm, since this can't be undone or resumed — but you'll still get a score and
  report for whatever you completed before stopping.
- Camera/microphone controls are visible in the interface but currently disabled — live video/audio
  interviewing isn't available yet.

## After the Interview

Once the interview ends (naturally or via Terminate), you'll land on a report showing:
- **Overall score** and a hire-signal read (e.g. "lean yes")
- **Summary** of how the conversation went
- **Top strengths** — what you did well
- **Key gaps** — where you fell short
- **Recommendations** — specific things to study or practice before your next real interview
- **Turn-by-turn scores** — a breakdown of each individual answer

Every past session (in progress, completed, or ended early) is listed on your **Dashboard**, along
with your score trend over time and an "Improvement Partner" panel summarizing recurring themes
across your recent sessions.

## Bring Your Own Key (BYOK)

By default, the app uses its own shared AI key so you can start immediately with no setup. If you'd
rather use your own — for a different model, or because you've used up your free interviews — go to
**Settings → Model & API key**. You can add a key for Groq, Google Gemini, OpenAI, or any other
OpenAI-compatible provider. Each provider's picker shows a link to where you can get a free or paid
key for that service. Your key is encrypted before it's stored; the app never displays it back to you
once saved, and it's only ever used for your own interview sessions.

## Account Settings

- **Password management**: set a password if you signed up via Google/GitHub (you don't have one by
  default), change your existing password, or reset a forgotten one by re-authenticating through a
  linked Google/GitHub account.
- **Linking identifiers**: if you signed up with just an email (e.g. via Google), you can add a phone
  number afterward, and vice versa.
- **API keys**: add, view (key itself is never shown again after saving), or remove BYOK keys per
  provider.

## FAQ

**Do I need to finish an interview once I start?**
No — use Terminate any time. You'll still get a report for what you completed.

**Can I redo an interview if I don't like how it went?**
Not the same session (nothing is resumable once ended), but you can always start a new one.

**Why did the interviewer ask about my specific project/company?**
If you uploaded a résumé and/or a job description, the interviewer uses that real information to ask
more specific, relevant questions instead of generic ones.

**What happens if I run out of free interviews?**
You'll see a message pointing you to Settings to add your own API key. Guest accounts get 1 free
interview; signed-up accounts get 2.

**Is my data private?**
Your interview transcripts, scores, and reports are tied to your account and not shared with other
users. BYOK keys are encrypted at rest and never displayed back to you.

## Known Limitations (current version)

- Live video/audio interviewing is not yet available — camera/mic controls are visible but inactive.
- Guest accounts are simple and easy to reset by clearing your browser data — they're meant for a
  quick first look, not a durable identity. Sign up for anything you want to keep.
- Company-specific question style currently covers a fixed set of well-known companies plus
  whatever can be found via web search for others — it's not a fully structured database of every
  company's actual interview process.
- Microsoft sign-in is not yet available (Google and GitHub are).
