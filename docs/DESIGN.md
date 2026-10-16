# Interface decisions

CueFlow is a focused desktop utility for people who already have a video and an SRT.
The primary action is synchronizing those two files. There is no account or onboarding.

The reference direction combines [Linear's changelog](https://linear.app/changelog)
with the single-action discipline of [Cron](https://cron.com), researched through Refero.
Linear provides the dominant near-black canvas, restrained text hierarchy, graphite
borders and 8 px containers. Cron contributes one orange primary action; the accent
is reserved for that action. Native system fonts replace proprietary reference fonts.

The window has a compact wordmark, a persistent language selector, two clearly labeled
file selectors, an output folder, collapsed advanced controls and one synchronization
button. Native dialogs and focus indicators support keyboard use. Progress and errors
remain in the window. A successful result shows the filename, timing adjustment and
an action to open its folder. The timeline is an explanatory diagram, not measured audio.

Use 32 px outer spacing, 24 px section spacing, 14 px body text and 32 px headings.
Background: #08090a. Surface: #141516. Text: #f7f8f8. Secondary text: #a6abb4.
Borders: #34343a. Primary action: #ff4700 with near-black text for contrast.
Avoid marketing illustrations, fake audio waveforms, distracting animation and heavy shadows.

The demo GIF must capture the actual Qt application and use an original synthetic fixture.
No movie, movie frame or third-party subtitle text belongs in this repository.
