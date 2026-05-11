import { type ChangeEvent, type ReactNode } from 'react'

/**
 * Question primitives. All five mirror the structure in
 * orpheus-questionnaire-s*.html and rely on the global classes defined in
 * orpheus-styles.css (`.question`, `.radio-option`, `.checkbox-option`,
 * `.scale-option`, etc.).
 *
 * The HTML prototype uses `:has(input:checked)` for selected-state styling,
 * which works equally well with React's controlled inputs because the
 * `checked` attribute is reflected in the DOM.
 */

interface QuestionShellProps {
  number: number
  text: string
  helper?: string
  children: ReactNode
}

function QuestionShell({ number, text, helper, children }: QuestionShellProps) {
  return (
    <div className="question">
      <div className="question-label">
        <span className="question-number">{number}</span>
        <label className="question-text">{text}</label>
      </div>
      {helper && <p className="question-helper">{helper}</p>}
      {children}
    </div>
  )
}

// ── Text question (textarea) ───────────────────────────────────────────

interface TextQuestionProps {
  number: number
  text: string
  helper?: string
  value: string | undefined
  onChange: (value: string) => void
}

export function TextQuestion({
  number,
  text,
  helper,
  value,
  onChange,
}: TextQuestionProps) {
  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <textarea
        placeholder="Your answer"
        value={value ?? ''}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
    </QuestionShell>
  )
}

// ── Radio question (single-select) ─────────────────────────────────────

export interface RadioOption {
  value: string
  label: string
}

interface RadioQuestionProps {
  number: number
  text: string
  helper?: string
  name: string
  options: readonly RadioOption[]
  value: string | undefined
  onChange: (value: string) => void
}

export function RadioQuestion({
  number,
  text,
  helper,
  name,
  options,
  value,
  onChange,
}: RadioQuestionProps) {
  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <div className="radio-group">
        {options.map((opt) => (
          <label className="radio-option" key={opt.value}>
            <input
              type="radio"
              name={name}
              value={opt.value}
              checked={value === opt.value}
              onChange={() => onChange(opt.value)}
            />
            <span className="radio-indicator" />
            <span className="option-text">{opt.label}</span>
          </label>
        ))}
      </div>
    </QuestionShell>
  )
}

// ── Radio with inline "Other" text input ───────────────────────────────

interface RadioWithOtherQuestionProps {
  number: number
  text: string
  helper?: string
  name: string
  /** All options including the "other" choice in its natural position. */
  options: readonly RadioOption[]
  /** Which option's value triggers the inline free-text input. */
  otherValue: string
  /** Currently selected option (may be `otherValue`). */
  value: string | undefined
  /** Free-text content of the "other" input, regardless of selection. */
  otherText: string | undefined
  onChange: (value: string) => void
  onOtherTextChange: (text: string) => void
}

/**
 * Radio group with one option that has an inline free-text input rendered
 * after its label (Q5 "Other:" and Q22 "Yes, I have or plan to have
 * support:" in the prototype). The "other" option keeps its natural
 * position in the option list — the prototype renders it last for Q5 and
 * second-of-three for Q22.
 */
export function RadioWithOtherQuestion({
  number,
  text,
  helper,
  name,
  options,
  otherValue,
  value,
  otherText,
  onChange,
  onOtherTextChange,
}: RadioWithOtherQuestionProps) {
  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <div className="radio-group">
        {options.map((opt) => {
          const isOther = opt.value === otherValue
          return (
            <label className="radio-option" key={opt.value}>
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={value === opt.value}
                onChange={() => onChange(opt.value)}
              />
              <span className="radio-indicator" />
              <span className="option-text">
                {opt.label}
                {isOther ? ' ' : ''}
              </span>
              {isOther && (
                <input
                  type="text"
                  className="other-input"
                  placeholder="Please describe"
                  value={otherText ?? ''}
                  onChange={(e) => {
                    onOtherTextChange(e.target.value)
                    // Auto-select "Other" when the user starts typing —
                    // matches the prototype's natural-feel behavior. If the
                    // radio was already on Other this is a no-op.
                    if (value !== otherValue && e.target.value.length > 0) {
                      onChange(otherValue)
                    }
                  }}
                />
              )}
            </label>
          )
        })}
      </div>
    </QuestionShell>
  )
}

// ── Checkbox with inline "Other" text input ────────────────────────────

export interface CheckboxOption {
  value: string
  label: string
}

interface CheckboxWithOtherQuestionProps {
  number: number
  text: string
  helper?: string
  name: string
  /** All options including the "other" choice in its natural position. */
  options: readonly CheckboxOption[]
  /** Which option's value triggers the inline free-text input. */
  otherValue: string
  /** Currently-selected option values (may include `otherValue`). */
  values: readonly string[] | undefined
  /** Free-text content of the "other" input, regardless of selection. */
  otherText: string | undefined
  onChange: (values: string[]) => void
  onOtherTextChange: (text: string) => void
}

/**
 * Multi-select with an "Other" option that reveals an inline free-text
 * input. Mirrors the behavior of `RadioWithOtherQuestion`:
 *
 *   - Selection order doesn't matter — output array follows the options'
 *     canonical display order so the saved JSONB is stable across edits.
 *   - Typing into the Other text input auto-checks the Other option if it
 *     isn't already checked, matching the prototype's "natural feel."
 *   - Unchecking Other preserves the typed text so the user can re-check
 *     without retyping (the parallel `qN_other` field is independent of
 *     whether Other is currently selected).
 */
export function CheckboxWithOtherQuestion({
  number,
  text,
  helper,
  name,
  options,
  otherValue,
  values,
  otherText,
  onChange,
  onOtherTextChange,
}: CheckboxWithOtherQuestionProps) {
  const selected = new Set(values ?? [])

  const toggle = (val: string) => {
    const next = new Set(selected)
    if (next.has(val)) next.delete(val)
    else next.add(val)
    onChange(options.map((o) => o.value).filter((v) => next.has(v)))
  }

  const ensureOtherSelected = () => {
    if (selected.has(otherValue)) return
    const next = new Set(selected)
    next.add(otherValue)
    onChange(options.map((o) => o.value).filter((v) => next.has(v)))
  }

  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <div className="checkbox-group">
        {options.map((opt) => {
          const isOther = opt.value === otherValue
          return (
            <label className="checkbox-option" key={opt.value}>
              <input
                type="checkbox"
                name={name}
                value={opt.value}
                checked={selected.has(opt.value)}
                onChange={() => toggle(opt.value)}
              />
              <span className="checkbox-indicator">
                <span className="checkbox-check">&#10003;</span>
              </span>
              <span className="option-text">
                {opt.label}
                {isOther ? ' ' : ''}
              </span>
              {isOther && (
                <input
                  type="text"
                  className="other-input"
                  placeholder="Please describe"
                  value={otherText ?? ''}
                  onChange={(e) => {
                    onOtherTextChange(e.target.value)
                    // Auto-select "Other" once the user actually types
                    // something. Mirrors RadioWithOtherQuestion's behavior.
                    if (e.target.value.length > 0) {
                      ensureOtherSelected()
                    }
                  }}
                />
              )}
            </label>
          )
        })}
      </div>
    </QuestionShell>
  )
}

