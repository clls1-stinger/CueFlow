# Desktop interface decisions

## Goal and reference lock

The user found the installed interface confusing. CueFlow 1.3.0 starts with the user's
problem: timing, language or text. It keeps the existing Linear/Cron-inspired near-black
canvas and orange primary action. This is a workflow redesign within the established
visual system, not a new identity. No generated imagery is needed.

Refero style searches returned no results during this iteration. The existing reference
lock remains the visual source; Refero's copywriting and craft guides supply plain action
labels, explicit next steps, keyboard focus and unsaved-work protection.

Product references inspected through Refero:

- [MonoDesk file upload flow](https://refero.design/flows/10847): an empty state with a clear file action, optional controls, progress, and a distinct successful outcome.
- [Rox document upload](https://refero.design/pages/42541549-f57f-403b-8606-dbb995c14772): one primary action and optional information separated from required input.
- [Lemon Squeezy upload modal](https://refero.design/pages/7b497600-7aa5-4f77-a0e2-4b398844cc33): a file-selection step with a clear return path and room for adding files.

## Decisions

| Decision | Source | Reason |
| --- | --- | --- |
| Three task choices, described in everyday language | User's confusion; copywriting guide | Explain the outcome before requesting files. |
| Preserve dark canvas, graphite borders, 8–10 px containers and orange action | Existing CueFlow reference lock | Keep the product recognizable; orange marks the main action. |
| Show filenames; keep full paths in tooltips | User's nontechnical workflow | Make the selected files recognizable. |
| Fold output location and advanced synchronization settings | Rox optional controls | A normal timing adjustment only needs video and subtitles. |
| Open → translate → review/save | MonoDesk flow | Show one stage at a time without an empty editing table. |
| Hide timestamp columns and conversion until requested | User's confusion | Editing dialogue should not require understanding time formats. |
| Consent before Google; editing remains available offline | Existing privacy contract | Explain when text leaves the device. |
| Separate completed translation from saved copy | MonoDesk completion states; craft guide | Prevent losing work by assuming translation saved the file. |
| Prompt only for unsaved edits or active translation, including Escape | Craft guide | Protect work without prompting after every harmless close. |

Body text is 14 px, section headings 18 px, page headings 32 px. Outer spacing is
28–32 px. Colors: background #08090a, surface #141516, text #f7f8f8, secondary
#a6abb4, border #34343a, primary action #ff4700 with near-black text. No decorative
waveform or status metric appears before a task.

Validation covers both interface languages, task navigation, file readiness, single
versus multiple audio tracks, offline editing, consent, translation retry, saving,
and unsaved-close protection. Screenshots and the GIF come from actual Qt windows
and synthetic fixtures. Real Google translation is verified separately from mocked
regression tests. No usability study with first-time users has been conducted yet.

## OpenSubtitles handoff

A secondary “Need subtitles?” action sits on the home screen, timing form and editor import step. The search dialog accepts an editable title suggestion from the video filename, opens the official site in the default browser, and offers a return action to choose the downloaded file. It does not store credentials or scrape/download results. The home-page action provides a fallback if the provider changes its search route. Automated requests received the provider's security challenge during validation; no live search-result or download success is claimed.
