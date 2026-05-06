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

// ── Checkbox question (multi-select) ───────────────────────────────────

export interface CheckboxOption {
  value: string
  label: string
}

interface CheckboxQuestionProps {
  number: number
  text: string
  helper?: string
  name: string
  options: readonly CheckboxOption[]
  values: readonly string[] | undefined
  onChange: (values: string[]) => void
}

export function CheckboxQuestion({
  number,
  text,
  helper,
  name,
  options,
  values,
  onChange,
}: CheckboxQuestionProps) {
  const selected = new Set(values ?? [])

  const toggle = (val: string) => {
    const next = new Set(selected)
    if (next.has(val)) next.delete(val)
    else next.add(val)
    // Preserve canonical order so saved JSONB is stable across edits.
    onChange(options.map((o) => o.value).filter((v) => next.has(v)))
  }

  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <div className="checkbox-group">
        {options.map((opt) => (
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
            <span className="option-text">{opt.label}</span>
          </label>
        ))}
      </div>
    </QuestionShell>
  )
}

// ── Scale question (1-5 with labels) ───────────────────────────────────

export interface ScaleOption {
  value: number
  label: string
}

interface ScaleQuestionProps {
  number: number
  text: string
  helper?: string
  name: string
  options: readonly ScaleOption[]
  value: number | undefined
  onChange: (value: number) => void
}

export function ScaleQuestion({
  number,
  text,
  helper,
  name,
  options,
  value,
  onChange,
}: ScaleQuestionProps) {
  return (
    <QuestionShell number={number} text={text} helper={helper}>
      <div className="scale-group">
        <div className="scale-options">
          {options.map((opt) => (
            <label className="scale-option" key={opt.value}>
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={value === opt.value}
                onChange={() => onChange(opt.value)}
              />
              <div className="scale-pip">{opt.value}</div>
              <span className="scale-label">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>
    </QuestionShell>
  )
}
