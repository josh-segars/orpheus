import { Link, useNavigate } from 'react-router-dom'

import {
  CheckboxWithOtherQuestion,
  RadioQuestion,
  RadioWithOtherQuestion,
  TextQuestion,
} from '../components/questionnaire/Questions'
import { useQuestionnaireDraft } from '../hooks/useQuestionnaire'
import { OTHER_OPTION } from '../types/questionnaire'

/**
 * Single-page intake questionnaire (ORPHEUS-33). Replaces the previous
 * 7-section flow shipped under ORPHEUS-18.
 *
 * Visual source of truth: `orpheus-questionnaire-v2.html`.
 *
 * Question text and option lists live inline so this file remains the
 * single source of truth for prompt-visible content (matches the
 * convention from the previous sections.tsx). If we ever localise, we'll
 * lift the strings into a content module.
 *
 * Completion is derived at read time by `isQuestionnaireComplete` against
 * the answers JSONB — there is no persisted completion flag. Both action
 * buttons flush any pending autosave and navigate back to Groundwork; the
 * Groundwork checklist row reflects completion via the same predicate.
 */

// Option-list helper: the persisted value and the rendered label are the
// same canonical string per the spec (the literal option text flows into
// both the JSONB answers and the narrative prompt).
const opt = (label: string) => ({ value: label, label })

const Q1_OPTIONS = [
  opt('Employed full-time'),
  opt('Employed full-time with outside advisory or consulting work'),
  opt('Independent consultant, advisor, or principal'),
  opt('Entrepreneur or founder'),
  opt('Between roles'),
  opt(OTHER_OPTION),
] as const

const Q2_OPTIONS = [
  opt('New employment'),
  opt('Board positions'),
  opt('Advisory or consulting work'),
  opt('Speaking opportunities'),
  opt('Thought leadership'),
  opt('Media or press visibility'),
  opt('Government or public sector opportunities'),
  opt('Investor or funding relationships'),
  opt("None of these — I'm not actively pursuing anything right now"),
  opt(OTHER_OPTION),
] as const

const Q3_OPTIONS = [
  opt('A specific transition or career moment'),
  opt("A concrete opportunity I'm pursuing"),
  opt("General concern that my online presence doesn't reflect my background"),
  opt("Curiosity — I want to understand how I'm being seen"),
  opt(OTHER_OPTION),
] as const

const Q4_OPTIONS = [
  opt('Passive — I have a profile but rarely post, comment, or engage'),
  opt('Occasional — I engage when something relevant comes up, but not consistently'),
  opt("Uncertain — I've started participating more but feel unsure about what I'm doing"),
  opt("Active but adrift — I post regularly but don't feel it's working strategically"),
  opt('Active and engaged — I post regularly and feel reasonably confident, but want an outside perspective'),
  opt(OTHER_OPTION),
] as const

const Q5_OPTIONS = [
  opt("Not comfortable — it doesn't reflect who I am or what I do"),
  opt("Somewhat comfortable — it's adequate but not optimal"),
  opt("Neutral — I haven't thought about it much"),
  opt("Fairly comfortable — but I know there's room to improve"),
  opt('Very comfortable — I just want an outside perspective'),
] as const

const Q6_OPTIONS = [
  opt("Low — I use it but don't really understand how it works"),
  opt('Moderate — I have a general sense but significant gaps'),
  opt('Fairly high — I understand the basics but not the deeper mechanics'),
  opt('High — I follow platform developments and understand how the system operates'),
] as const

const Q7_OPTIONS = [
  opt("I haven't really considered it"),
  opt("I suspect it matters but don't fully understand how"),
  opt('I understand it matters and have tried to address it'),
  opt("I understand it well — that's precisely why I'm here"),
] as const

const Q8_OPTIONS = [
  opt('My profile accurately reflects my expertise and current work'),
  opt('The right people are finding me and understanding what I offer'),
  opt('I have a sustainable, comfortable approach to participating professionally'),
  opt('I feel confident my presence is working for me, not against me'),
  opt('All of the above'),
] as const

// ── Page ───────────────────────────────────────────────────────────────

export function QuestionnairePage() {
  const { answers, updateAnswer, flush, isSaving } = useQuestionnaireDraft()
  const navigate = useNavigate()

  const handleSaveAndReturn = async () => {
    await flush()
    navigate('/groundwork')
  }

  return (
    <main className="main-interior">
      <Link to="/groundwork" className="back-link">
        <span className="back-arrow">&#8249;</span> Groundwork Checklist
      </Link>

      <div className="section-header">
        <span className="section-eyebrow">Intake Questionnaire</span>
        <h1 className="section-title">Intake Questionnaire</h1>
        <p className="section-intro">
          Completed prior to your Strategic Presence Diagnostic —
          approximately 5 minutes. There are no right or wrong answers. The
          more honestly you respond, the more useful the session will be.
        </p>
      </div>

      <div className="questions">
        <CheckboxWithOtherQuestion
          number={1}
          text="Which of the following best describes your current situation?"
          helper="Select all that apply."
          name="q1"
          options={Q1_OPTIONS}
          otherValue={OTHER_OPTION}
          values={answers.q1}
          otherText={answers.q1_other}
          onChange={(v) => updateAnswer('q1', v)}
          onOtherTextChange={(t) => updateAnswer('q1_other', t)}
        />
        <CheckboxWithOtherQuestion
          number={2}
          text="Are you actively pursuing any of the following?"
          helper="Select all that apply."
          name="q2"
          options={Q2_OPTIONS}
          otherValue={OTHER_OPTION}
          values={answers.q2}
          otherText={answers.q2_other}
          onChange={(v) => updateAnswer('q2', v)}
          onOtherTextChange={(t) => updateAnswer('q2_other', t)}
        />
        <RadioWithOtherQuestion
          number={3}
          text="What is driving your interest in this engagement now?"
          name="q3"
          options={Q3_OPTIONS}
          otherValue={OTHER_OPTION}
          value={answers.q3}
          otherText={answers.q3_other}
          onChange={(v) => updateAnswer('q3', v)}
          onOtherTextChange={(t) => updateAnswer('q3_other', t)}
        />
        <RadioWithOtherQuestion
          number={4}
          text="How would you describe your current approach to LinkedIn?"
          name="q4"
          options={Q4_OPTIONS}
          otherValue={OTHER_OPTION}
          value={answers.q4}
          otherText={answers.q4_other}
          onChange={(v) => updateAnswer('q4', v)}
          onOtherTextChange={(t) => updateAnswer('q4_other', t)}
        />
        <RadioQuestion
          number={5}
          text="How comfortable are you with your current LinkedIn presence?"
          name="q5"
          options={Q5_OPTIONS}
          value={answers.q5}
          onChange={(v) => updateAnswer('q5', v)}
        />
        <RadioQuestion
          number={6}
          text="How would you rate your familiarity with how LinkedIn actually works as a professional visibility system?"
          name="q6"
          options={Q6_OPTIONS}
          value={answers.q6}
          onChange={(v) => updateAnswer('q6', v)}
        />
        <RadioQuestion
          number={7}
          text="How well do you understand the impact your online presence has on how you're discovered and evaluated by the people who matter most to your work?"
          name="q7"
          options={Q7_OPTIONS}
          value={answers.q7}
          onChange={(v) => updateAnswer('q7', v)}
        />
        <RadioQuestion
          number={8}
          text="What does a successful online presence look like for you 12 months from now?"
          name="q8"
          options={Q8_OPTIONS}
          value={answers.q8}
          onChange={(v) => updateAnswer('q8', v)}
        />
        <TextQuestion
          number={9}
          text="Is there anything else you'd like us to know before we begin?"
          helper='If nothing comes to mind, you can simply type "Nothing to add."'
          value={answers.q9}
          onChange={(v) => updateAnswer('q9', v)}
        />
      </div>

      <div className="actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={handleSaveAndReturn}
          disabled={isSaving}
        >
          Save My Answers
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={handleSaveAndReturn}
          disabled={isSaving}
        >
          This Section is Complete
        </button>
      </div>
    </main>
  )
}
