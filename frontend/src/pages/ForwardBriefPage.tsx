import { Link, useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import './ForwardBriefPage.css'

/**
 * Forward Brief — client-facing narrative delivered after the Signal
 * Score. The content is backend-generated Markdown (400–600 words) held
 * on `narratives.forward_brief`. We render a constrained subset of
 * Markdown (H2 / paragraphs / unordered lists) locally rather than pull
 * in a parser dependency — see renderForwardBriefMarkdown below.
 */
export function ForwardBriefPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, error } = useJob(jobId)

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your Forward Brief&hellip;</div>
      </main>
    )
  }

  if (error || !job) {
    return (
      <main className="main-interior">
        <div className="page-status">
          We couldn&rsquo;t load this report. Please try again.
        </div>
      </main>
    )
  }

  if (job.state !== 'complete' || !job.result) {
    return (
      <main className="main-interior">
        <div className="section-header">
          <div className="section-eyebrow">Analysis in Progress</div>
          <h2 className="section-title">
            Your Forward Brief is still being prepared
          </h2>
          <p className="section-intro">
            This page will refresh automatically when the analysis is complete.
          </p>
        </div>
      </main>
    )
  }

  const { forward_brief } = job.result.narratives
  const blocks = parseForwardBriefMarkdown(forward_brief)

  return (
    <main className="main-interior">
      <div className="section-header">
        <div className="section-eyebrow">Forward Brief</div>
        <h1 className="section-title">Your Path to a Stronger Signal</h1>
      </div>

      <p className="section-intro">
        Your Forward Brief translates the Signal Score diagnostic into action.
        Work through it in sequence — the priorities compound.
      </p>

      <article className="forward-brief-prose">
        {blocks.map((block, i) => renderBlock(block, i))}
      </article>

      <div className="forward-brief-next">
        <div className="section-eyebrow">Next Steps</div>
        <p className="forward-brief-next-body">
          Andrew will review these priorities with you directly, sequence them
          against your current workload, and set milestones for the 90 days
          ahead. Bring questions, pushbacks, and additions to that
          conversation.
        </p>
      </div>

      <div className="actions">
        <Link to={`/jobs/${job.id}`} className="btn-secondary">
          &larr; Return to Signal Score
        </Link>
        <Link to={`/jobs/${job.id}/cheat-sheet`} className="btn-primary">
          View Cheat Sheet &rarr;
        </Link>
      </div>
    </main>
  )
}

// --- Markdown rendering ---------------------------------------------------
//
// Constrained subset: `## Heading`, `- bullet`, blank-line-separated
// paragraphs. Inline: `**bold**` → <strong>, `*em*` → <em>. No HTML pass-
// through, no links, no images — the backend prompt produces plain
// narrative text in these shapes only.

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; items: string[] }

function parseForwardBriefMarkdown(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      i++
      continue
    }

    if (line.startsWith('## ')) {
      blocks.push({ kind: 'heading', text: line.slice(3).trim() })
      i++
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, '').trim())
        i++
      }
      blocks.push({ kind: 'list', items })
      continue
    }

    // Paragraph — gather contiguous non-blank, non-heading, non-list lines.
    const paragraphLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('## ') &&
      !/^[-*]\s+/.test(lines[i])
    ) {
      paragraphLines.push(lines[i])
      i++
    }
    blocks.push({ kind: 'paragraph', text: paragraphLines.join(' ').trim() })
  }

  return blocks
}

function renderBlock(block: Block, key: number) {
  switch (block.kind) {
    case 'heading':
      return (
        <h2 className="forward-brief-heading" key={key}>
          {renderInline(block.text)}
        </h2>
      )
    case 'paragraph':
      return (
        <p className="forward-brief-paragraph" key={key}>
          {renderInline(block.text)}
        </p>
      )
    case 'list':
      return (
        <ul className="forward-brief-list" key={key}>
          {block.items.map((item, j) => (
            <li key={j}>{renderInline(item)}</li>
          ))}
        </ul>
      )
  }
}

/**
 * Inline formatter for **bold** and *italic*. Non-greedy matches; escapes
 * are ignored (backend prompt doesn't produce them). Unrecognized markers
 * fall through as plain text.
 */
function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  const re = /\*\*(.+?)\*\*|\*(.+?)\*/g
  let last = 0
  let match: RegExpExecArray | null
  let key = 0

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      out.push(text.slice(last, match.index))
    }
    if (match[1] !== undefined) {
      out.push(<strong key={key++}>{match[1]}</strong>)
    } else if (match[2] !== undefined) {
      out.push(<em key={key++}>{match[2]}</em>)
    }
    last = re.lastIndex
  }
  if (last < text.length) {
    out.push(text.slice(last))
  }
  return out
}
