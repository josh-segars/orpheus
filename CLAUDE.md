# Orpheus Social — Project Context

Orpheus Social is a client portal and diagnostic tool for **Andrew Segars'
Strategic Digital Presence Advisory** practice. It guides senior executive
clients through a structured data-gathering phase ("Groundwork"), then
delivers a **Signal Score** diagnostic and **Forward Brief** action plan.

Built by Josh Segars. No framework — pure HTML and CSS. No JavaScript.

---

## File Naming Convention

```
orpheus-[screen]-[variant/version].html
orpheus-styles.css
```

All files live flat in the repo root. Assets go in `assets/screenshots/`.

---

## Design System

### Fonts
- **Source Serif 4** — headings, numbers, display (variable, use `opsz` axis)
- **Source Sans 3** — body, UI, labels
- Both loaded from Google Fonts in each HTML file's `<head>`

### Color Tokens (defined in `orpheus-styles.css` `:root`)
```
--deep-slate:     #1C2B3A   (primary dark, nav bg, buttons)
--warm-gold:      #C4902A   (accent, active states, highlights)
--warm-ivory:     #F9F6F0   (page background)
--warm-parchment: #EDE9E1   (card/input backgrounds)
--warm-text:      #271D10   (body text)
--warm-stone:     #7A6A56   (secondary text, placeholders)
--warm-border:    #DDD5C8   (borders, dividers)
```

### Border Radius
10px throughout — no exceptions.

### Input Interaction Pattern
`:has(input:checked)` CSS selector for radio/checkbox selected states.
No JavaScript for any UI behavior.

---

## Shared Stylesheet (`orpheus-styles.css`)

Contains all shared patterns. Do not duplicate these in page `<style>` blocks:
- Reset, body, tokens
- `.nav`, `.wordmark`, `.nav-client` (navigation)
- `.footer`, `.wordmark-sm`, `.footer-links`
- `.back-link`, `.back-arrow`
- `.main-interior` (interior page layout — max-width 820px)
- `.section-header`, `.section-eyebrow`, `.section-title`, `.section-intro`
- `.questions`, `.question`, `.question-label`, `.question-number`, `.question-text`, `.question-helper`
- `textarea`
- `.radio-group`, `.radio-option`, `.radio-indicator`, `.option-text`
- `.other-input` (inline text inside a radio option)
- `.checkbox-group`, `.checkbox-option`, `.checkbox-indicator`, `.checkbox-check`
- `.scale-group`, `.scale-options`, `.scale-option`, `.scale-pip`, `.scale-label`
- `.actions`, `.btn-primary`, `.btn-secondary`
- `.info-notice`, `.info-notice-text`, `.info-notice-label`, `.info-notice-body`
- `.steps`, `.step`, `.step-number`, `.step-content`, `.step-title`, `.step-body`, `.step-note`
- `.screenshot-placeholder`, `.screenshot-label`
- `.upload-section`, `.upload-label`, `.upload-area`, `.upload-icon`, `.upload-primary`, `.upload-secondary`, `.upload-file-type`

Page-specific styles (welcome layout, groundwork checklist, etc.) stay in
a `<style>` block in the page's `<head>`.

---

## Button Naming

| Class | Use |
|---|---|
| `.btn-primary` | Primary action ("This Section is Complete", "This Step is Complete") |
| `.btn-secondary` | Secondary action ("Save My Answers", "Save My Progress") |
| `.btn-start` | Welcome page only ("Get Started") |
| `.btn-complete` | Groundwork page only ("My Groundwork is Complete") — has disabled/active states |

---

## Portal Pages & Status

| File | Screen | Status |
|---|---|---|
| `orpheus-welcome-v6.html` | Welcome / entry | ✅ Complete |
| `orpheus-groundwork-v1.html` | Groundwork Checklist | ✅ Complete |
| `orpheus-linkedin-step1.html` | LinkedIn Data — Step 1: Request Archive | ✅ Complete |
| `orpheus-linkedin-step2.html` | LinkedIn Data — Step 2: Export Analytics | ✅ Complete |
| `orpheus-questionnaire-s1.html` | Q: Professional Identity (Q1–Q4) | ✅ Complete |
| `orpheus-questionnaire-s2.html` | Q: Career Stage & Context (Q5–Q7) | ✅ Complete |
| `orpheus-questionnaire-s3.html` | Q: Target Audiences (Q8–Q10) | ✅ Complete |
| `orpheus-questionnaire-s4.html` | Q: Goals (Q11–Q13) | ✅ Complete |
| `orpheus-questionnaire-s5.html` | Q: Current LinkedIn Relationship (Q14–Q17) | ✅ Complete |
| `orpheus-questionnaire-s6.html` | Q: Voice & Style (Q18–Q20) | ✅ Complete |
| `orpheus-questionnaire-s7.html` | Q: Practical Parameters (Q21–Q23) | ✅ Complete |
| `orpheus-analysis.html` | Analysis in Progress (holding state) | 🔲 Not started |
| `orpheus-signal-score.html` | Signal Score delivery | 🔲 Not started |
| `orpheus-forward-brief.html` | Forward Brief delivery | 🔲 Not started |

---

## Navigation Flow

```
Welcome → Groundwork Checklist → [any item] → [item page] → Groundwork Checklist
                                                                      ↓
                                                         My Groundwork is Complete
                                                                      ↓
                                                         Analysis in Progress
                                                                      ↓
                                                              Signal Score
                                                                      ↓
                                                            Forward Brief
```

All questionnaire sections and LinkedIn steps return to Groundwork Checklist
via back link and both action buttons. Navigation is non-linear — clients
can complete items in any order.

---

## LinkedIn Data Inputs

Two files collected from clients during Groundwork:

1. **ZIP archive** — from LinkedIn Settings > Data privacy > Download your data >
   "Download larger data archive". Contains CSVs: Profile, Positions, Education,
   Skills, Connections, Recommendations, Endorsements, Shares, Inferences_about_you, etc.
   No analytics data in ZIP.

2. **Analytics XLSX** — from linkedin.com/analytics/creator/content/ (accessed via
   "Post impressions" link in feed left column). Export set to "Past 365 days".
   Sheets: DISCOVERY, ENGAGEMENT, TOP POSTS, FOLLOWERS, DEMOGRAPHICS.

PDF export was evaluated and deemed redundant — ZIP CSVs contain same profile data.

---

## Questionnaire Questions Reference

| # | Section | Type |
|---|---|---|
| 1–4 | Professional Identity | Open text |
| 5 | Career Stage & Context | Radio (5 options + Other w/ inline text) |
| 6 | Career Stage & Context | Radio (4 options) |
| 7 | Career Stage & Context | Open text |
| 8–10 | Target Audiences | Open text |
| 11 | Goals | Open text |
| 12 | Goals | Checkboxes (7 options, select all that apply) |
| 13 | Goals | Open text |
| 14 | Current LinkedIn Relationship | Radio (5 options) |
| 15 | Current LinkedIn Relationship | Radio (5 options) |
| 16 | Current LinkedIn Relationship | Scale 1–5 |
| 17 | Current LinkedIn Relationship | Open text |
| 18–20 | Voice & Style | Open text |
| 21 | Practical Parameters | Radio (4 options) |
| 22 | Practical Parameters | Radio (3 options, "Yes" has inline text) |
| 23 | Practical Parameters | Open text |

---

## Decisions Made

- No JavaScript — all interaction via CSS `:has()` selector
- No PDF export step (redundant with ZIP)
- Data retention: delete after AI processing; Signal Score is the durable record
- Confidentiality / AI data handling policy: deferred, to be discussed with Andrew
- Screenshot assets for LinkedIn instruction pages: deferred
- "My Groundwork is Complete" button stays disabled (`opacity: 0.35`) until
  completion logic is implemented (requires JS or backend)
- Client name "Jane Doe" is the placeholder throughout — will be personalized per client

---

## Deferred / Pending

- Screenshot assets for LinkedIn step pages (3 in step1, 3 in step2)
- Signal Score document structure (discuss with Andrew)
- Confidentiality policy and AI data handling disclosure
- Backend / form submission (currently all front-end static)
- Analysis in Progress, Signal Score, and Forward Brief screens
