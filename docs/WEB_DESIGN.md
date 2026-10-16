# CueFlow web design reference lock

A browser version of the existing CueFlow utility, for people with a film and an SRT.
The task is choosing two files, synchronizing, and downloading the corrected SRT.
No account, cloud upload, or onboarding is necessary.

## Reference lock

Refero research reviewed Cron Calendar, Electronic Materials Office and Pipe styles,
plus Anam's file selection screen and six-step upload flow, and Appwrite's completion
screen. Search directions: dark developer tools, audio software, and Cron productivity.
The first two searches returned no results; the third supplied the three full styles.

The existing CueFlow desktop system remains the build target. Cron is the dominant
web reference: a contained, near-black cockpit, clear white type, flat surfaces and
one orange action. Borrow only Pipe's quiet header and Electronic Materials Office's
monochrome outline icons. Do not borrow its photography, violet links or soft corners.
The working tool occupies the product showcase area; no decorative fake waveform.

Tokens: background #08090a, surface #141516, border #34343a, text #f7f8f8,
secondary #a6abb4, CTA #ff4700 with dark text. System sans-serif, 48px desktop heading,
34px mobile heading, 16px body, 13px metadata. 8px panels, 4px buttons, 24px gaps.
No gradients, giant hero, decorative serif words, shadows or marketing card grid.

## Decision ledger

| Decision | Source | Role | Reason |
| --- | --- | --- | --- |
| Dark canvas and orange primary button | Existing CueFlow + Cron | CTA-only accent | Continue the desktop identity and make the next action clear |
| File name, size and replace action | Anam file selection | Confirm the selected local input | Catch selection errors before processing |
| Progress, cancel, retry and explicit download | Anam flow + Appwrite completion | Processing and success feedback | Keep the entire journey on one screen |
| Native file controls, visible focus, 44px targets | Refero craft + accessibility | Input mechanics | Keyboard and mobile use |
| Settings collapsed; track choice only when useful | User's request for ease | Progressive disclosure | Two files are enough for the common case |
| GitHub and desktop links in header/footer | User request | Repository and fallback navigation | Make source and native version easy to find |
| Local browser processing | Movie sizes + privacy | Architecture | No movie upload or server CPU cost |

Reference links: [Cron](https://cron.com),
[Electronic Materials Office](https://electronicmaterialsoffice.com),
[Pipe](https://pipe.com),
[Anam screen](https://refero.design/pages/2732a937-c497-4a1e-b589-ff7b51858fc4),
[Anam flow](https://refero.design/flows/12937),
[Appwrite completion](https://refero.design/pages/b9ebdcdd-2812-4b38-b013-c9ffa2fd631f).

## Offline extension

The user's follow-up adds direct desktop downloads, suggested hardware and Android.
Keep the existing dark reference lock: monochrome download rows with the CueFlow
icon; no additional CTA accent. Four desktop links name the OS and architecture.
Android uses a separate installable-web-app row with explicit installation and
offline preparation actions. Put hardware suggestions in an expandable section,
keeping the main synchronization task first.
