/**
 * Seven questionnaire section pages, ported from
 * orpheus-questionnaire-s1..s7.html. Each is a thin wrapper over
 * SectionLayout that:
 *
 *   1. Pulls the shared draft + autosave from `useSectionDraft`.
 *   2. Wires controlled inputs through the question primitives.
 *   3. Maps "Save My Answers" → flush() (no completion flag).
 *   4. Maps "This Section is Complete" → flush(sectionId) (sets the flag).
 *
 * Question text and option lists live inline so the React file is the
 * single source of truth for prompt-visible content. If we ever localise
 * the questionnaire, we'll lift these into a content module.
 */

import { useSectionDraft } from '../../hooks/useQuestionnaire'
import { SectionLayout } from '../../components/questionnaire/SectionLayout'
import {
  CheckboxQuestion,
  RadioQuestion,
  RadioWithOtherQuestion,
  ScaleQuestion,
  TextQuestion,
} from '../../components/questionnaire/Questions'
import type { SectionId } from '../../types/questionnaire'

// Section 1 — Professional Identity (Q1–Q4, all textarea) ──────────────

export function Section1Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={1}
      title="Professional Identity"
      intro="These questions help us understand how you see yourself professionally, independent of how LinkedIn currently represents you."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's1')}
      isSaving={isSaving}
    >
      <TextQuestion
        number={1}
        text="What is your current professional role or focus?"
        helper="If you are in transition, describe where you are now and where you are heading."
        value={answers.q1}
        onChange={(v) => updateAnswer('q1', v)}
      />
      <TextQuestion
        number={2}
        text="How would you describe your core area of expertise in two or three sentences?"
        helper="Think about how you would explain it to a senior peer in your field — not an elevator pitch, just a clear description."
        value={answers.q2}
        onChange={(v) => updateAnswer('q2', v)}
      />
      <TextQuestion
        number={3}
        text="What are the two or three most important things you want people to understand about your professional background when they encounter you on LinkedIn?"
        value={answers.q3}
        onChange={(v) => updateAnswer('q3', v)}
      />
      <TextQuestion
        number={4}
        text="Are there specific topics, issues, or domains where you have genuine depth and want to be recognized as a credible voice?"
        value={answers.q4}
        onChange={(v) => updateAnswer('q4', v)}
      />
    </SectionLayout>
  )
}

// Section 2 — Career Stage & Context (Q5 radio+other, Q6 radio, Q7 text)

const Q5_OPTIONS = [
  {
    value: 'transitioning',
    label:
      'Transitioning out of an institutional role into advisory, consulting, or portfolio work',
  },
  {
    value: 'independent',
    label:
      'Already working as an independent advisor, consultant, or principal',
  },
  {
    value: 'leading',
    label:
      'Currently leading an organization and looking to strengthen my public presence',
  },
  {
    value: 'opportunities',
    label:
      'Exploring specific new opportunities: board roles, speaking, public commentary, or similar',
  },
  { value: 'other', label: 'Other:' },
] as const

const Q6_OPTIONS = [
  { value: 'under6', label: 'Less than 6 months' },
  { value: '6to12', label: '6 months to 1 year' },
  { value: '1to3', label: '1 to 3 years' },
  { value: 'over3', label: 'More than 3 years' },
] as const

export function Section2Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={2}
      title="Career Stage & Context"
      intro="Understanding where you are in your professional journey helps us calibrate the diagnostic against what is actually relevant for your situation."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's2')}
      isSaving={isSaving}
    >
      <RadioWithOtherQuestion
        number={5}
        text="Which of the following best describes your current situation?"
        helper="Select the one that fits best."
        name="q5"
        options={Q5_OPTIONS}
        otherValue="other"
        value={answers.q5}
        otherText={answers.q5_other}
        onChange={(v) => updateAnswer('q5', v)}
        onOtherTextChange={(t) => updateAnswer('q5_other', t)}
      />
      <RadioQuestion
        number={6}
        text="How long have you been in your current role or situation?"
        name="q6"
        options={Q6_OPTIONS}
        value={answers.q6}
        onChange={(v) => updateAnswer('q6', v)}
      />
      <TextQuestion
        number={7}
        text="Is there a specific professional transition, opportunity, or milestone driving your interest in this advisory now?"
        helper="Optional, but helpful context."
        value={answers.q7}
        onChange={(v) => updateAnswer('q7', v)}
      />
    </SectionLayout>
  )
}

// Section 3 — Target Audiences (Q8–Q10, all textarea) ──────────────────

export function Section3Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={3}
      title="Target Audiences"
      intro="Your LinkedIn presence is a signal directed at specific people. These questions help us understand who you most want to reach and what you want them to take away."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's3')}
      isSaving={isSaving}
    >
      <TextQuestion
        number={8}
        text="Who are the most important people you want to reach with your LinkedIn presence?"
        helper="Think in terms of roles, industries, or types of people — not specific individuals."
        value={answers.q8}
        onChange={(v) => updateAnswer('q8', v)}
      />
      <TextQuestion
        number={9}
        text="What do you want those people to think, feel, or do differently after encountering you on LinkedIn?"
        helper="What impression do you want to leave? What action, if any, do you hope to prompt?"
        value={answers.q9}
        onChange={(v) => updateAnswer('q9', v)}
      />
      <TextQuestion
        number={10}
        text="Are there specific organizations, communities, or professional networks where visibility matters most to you?"
        helper="Optional. Name them if it's useful."
        value={answers.q10}
        onChange={(v) => updateAnswer('q10', v)}
      />
    </SectionLayout>
  )
}

// Section 4 — Goals (Q11 text, Q12 multi-checkbox, Q13 text) ───────────

const Q12_OPTIONS = [
  { value: 'advisory', label: 'Inbound inquiries for advisory or consulting engagements' },
  { value: 'board', label: 'Board or governance opportunities' },
  { value: 'speaking', label: 'Speaking invitations' },
  { value: 'media', label: 'Media or press commentary requests' },
  { value: 'recruiting', label: 'Recruiting or talent attraction' },
  { value: 'partnership', label: 'Partnership or co-investment interest' },
  { value: 'recognition', label: 'Peer recognition within my industry or field' },
] as const

export function Section4Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={4}
      title="Goals"
      intro="Knowing what you are actually trying to accomplish helps us focus the diagnostic on what matters for your specific situation."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's4')}
      isSaving={isSaving}
    >
      <TextQuestion
        number={11}
        text="What does success look like for your LinkedIn presence over the next 12 months?"
        helper="Describe the outcome in whatever terms feel most meaningful to you."
        value={answers.q11}
        onChange={(v) => updateAnswer('q11', v)}
      />
      <CheckboxQuestion
        number={12}
        text="Which of the following outcomes are you actively seeking?"
        helper="Select all that apply."
        name="q12"
        options={Q12_OPTIONS}
        values={answers.q12}
        onChange={(vs) => updateAnswer('q12', vs)}
      />
      <TextQuestion
        number={13}
        text="Is there anything specific you are trying to avoid in how you are perceived or positioned?"
        helper="Optional, but useful context for the diagnostic."
        value={answers.q13}
        onChange={(v) => updateAnswer('q13', v)}
      />
    </SectionLayout>
  )
}

// Section 5 — Current LinkedIn Relationship (Q14 radio, Q15 radio, Q16 scale, Q17 text) ─

const Q14_OPTIONS = [
  { value: 'active', label: 'I post regularly and engage actively' },
  { value: 'occasional', label: "I post occasionally but don't have a consistent cadence" },
  { value: 'lurker', label: 'I rarely post but check in to follow others' },
  { value: 'dormant', label: 'I have not posted in more than a year' },
  { value: 'profile-only', label: 'I maintain my profile but avoid posting entirely' },
] as const

const Q15_OPTIONS = [
  { value: 'enjoy', label: 'I enjoy it and find it natural' },
  { value: 'value-but-time', label: 'I see the value but find it time-consuming' },
  { value: 'culture', label: 'I find the tone or culture of the platform off-putting' },
  { value: 'uncertain', label: 'I feel uncertain about what to say or how to say it' },
  { value: 'dislike', label: 'I actively dislike it and avoid it' },
] as const

const Q16_OPTIONS = [
  { value: 1, label: 'Not at all — it significantly undersells me' },
  { value: 2, label: 'Somewhat unsatisfied' },
  { value: 3, label: 'Neutral — adequate but not compelling' },
  { value: 4, label: 'Mostly satisfied' },
  { value: 5, label: 'Very satisfied — it represents me well' },
] as const

export function Section5Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={5}
      title="Current LinkedIn Relationship"
      intro="Your existing habits and feelings about LinkedIn shape what is realistic to recommend. There are no right or wrong answers here."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's5')}
      isSaving={isSaving}
    >
      <RadioQuestion
        number={14}
        text="How would you describe your current approach to LinkedIn?"
        helper="Select the one that fits best."
        name="q14"
        options={Q14_OPTIONS}
        value={answers.q14}
        onChange={(v) => updateAnswer('q14', v)}
      />
      <RadioQuestion
        number={15}
        text="How do you feel about posting and engaging on LinkedIn?"
        helper="Select the one that fits best."
        name="q15"
        options={Q15_OPTIONS}
        value={answers.q15}
        onChange={(v) => updateAnswer('q15', v)}
      />
      <ScaleQuestion
        number={16}
        text="How satisfied are you with how your current LinkedIn profile represents you?"
        helper="Select a number from 1 to 5."
        name="q16"
        options={Q16_OPTIONS}
        value={answers.q16}
        onChange={(v) => updateAnswer('q16', v)}
      />
      <TextQuestion
        number={17}
        text="Is there anything specific about your current profile or LinkedIn presence that you know needs attention?"
        helper="Optional. Gaps, outdated sections, anything that has been nagging at you."
        value={answers.q17}
        onChange={(v) => updateAnswer('q17', v)}
      />
    </SectionLayout>
  )
}

// Section 6 — Voice & Style (Q18–Q20, all textarea) ────────────────────

export function Section6Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={6}
      title="Voice & Style"
      intro="Any recommendations we make for your content or profile language should sound like you. These questions help us understand how you naturally communicate."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's6')}
      isSaving={isSaving}
    >
      <TextQuestion
        number={18}
        text="How would you describe your professional communication style?"
        helper="Think about how you write emails, give presentations, or communicate with peers — formal or informal, direct or discursive, data-driven or narrative."
        value={answers.q18}
        onChange={(v) => updateAnswer('q18', v)}
      />
      <TextQuestion
        number={19}
        text="Are there people whose LinkedIn presence you admire? If so, what specifically works about how they show up?"
        helper="Optional. Name them or describe the quality — either is useful."
        value={answers.q19}
        onChange={(v) => updateAnswer('q19', v)}
      />
      <TextQuestion
        number={20}
        text="Is there anything you want to actively avoid in terms of tone, style, or subject matter on LinkedIn?"
        helper="Optional. Things that feel inauthentic, off-brand, or that you've seen others do and want no part of."
        value={answers.q20}
        onChange={(v) => updateAnswer('q20', v)}
      />
    </SectionLayout>
  )
}

// Section 7 — Practical Parameters (Q21 radio, Q22 radio+other, Q23 text)

const Q21_OPTIONS = [
  { value: 'under30', label: 'Less than 30 minutes' },
  { value: '30to60', label: '30 minutes to 1 hour' },
  { value: '1to3hrs', label: '1 to 3 hours' },
  { value: 'over3hrs', label: 'More than 3 hours' },
] as const

const Q22_OPTIONS = [
  { value: 'solo', label: 'No, I handle everything myself' },
  { value: 'yes', label: 'Yes, I have or plan to have support:' },
  { value: 'unsure', label: 'Not sure yet' },
] as const

export function Section7Page() {
  const { answers, updateAnswer, flush, isSaving } = useSectionDraft()
  return (
    <SectionLayout
      sectionNumber={7}
      title="Practical Parameters"
      intro="The most useful recommendations are ones a person can actually act on. These last questions help us calibrate what to suggest given your real-world constraints."
      onSave={() => flush()}
      onComplete={() => flushComplete(flush, 's7')}
      isSaving={isSaving}
    >
      <RadioQuestion
        number={21}
        text="How much time are you realistically able to dedicate to LinkedIn activity each week?"
        helper="Be honest — we want recommendations that fit your life, not an idealized version of it."
        name="q21"
        options={Q21_OPTIONS}
        value={answers.q21}
        onChange={(v) => updateAnswer('q21', v)}
      />
      <RadioWithOtherQuestion
        number={22}
        text="Do you work with or plan to work with any support for your LinkedIn content?"
        helper="For example, a communications professional, EA, or writing collaborator."
        name="q22"
        options={Q22_OPTIONS}
        otherValue="yes"
        value={answers.q22}
        otherText={answers.q22_other}
        onChange={(v) => updateAnswer('q22', v)}
        onOtherTextChange={(t) => updateAnswer('q22_other', t)}
      />
      <TextQuestion
        number={23}
        text="Is there anything else that would be helpful for us to know as we begin this process?"
        helper="Open floor. Anything at all."
        value={answers.q23}
        onChange={(v) => updateAnswer('q23', v)}
      />
    </SectionLayout>
  )
}

// Helper — wraps `flush(sectionId)` so onComplete handlers stay one-liners.
async function flushComplete(
  flush: (sectionId?: SectionId) => Promise<void>,
  sectionId: SectionId,
): Promise<void> {
  await flush(sectionId)
}
