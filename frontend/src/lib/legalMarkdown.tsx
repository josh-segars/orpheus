/**
 * Minimal markdown → React renderer for the legal documents (ORPHEUS-125).
 *
 * Deliberately NOT a general-purpose markdown library. The canonical
 * Privacy Policy / Terms of Service text is committed to the repo as
 * markdown (src/content/legal/*.md) so the §19 change-notice obligation
 * has a versioned record of exactly what was published when — and this
 * renderer handles precisely the constructs those two documents use:
 *
 *   #  / ## / ###   headings
 *   - item          unordered lists
 *   1. item         ordered lists (numbering from the literal text)
 *   | a | b |       GFM tables with a |---| separator row
 *   **bold**        inline bold
 *   [text](url)     inline links (external — legal docs link out only)
 *   blank line      paragraph separator
 *
 * Anything outside that subset renders as plain paragraph text rather
 * than failing — and the page tests pin the constructs we rely on, so a
 * future document edit that introduces new syntax fails loudly in CI
 * instead of shipping as visible markdown soup. Adding a dependency
 * (react-markdown + remark-gfm) was considered and skipped: the input is
 * trusted first-party text with a fixed dialect, and the repo's posture
 * is minimal runtime dependencies.
 */

import { Fragment, type ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Inline: **bold**, [text](url), plain text
// ---------------------------------------------------------------------------

const INLINE_TOKEN = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE_TOKEN)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key}>{part.slice(2, -2)}</strong>
    }
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part)
    if (link) {
      return (
        <a key={key} href={link[2]} target="_blank" rel="noopener noreferrer">
          {link[1]}
        </a>
      )
    }
    return <Fragment key={key}>{part}</Fragment>
  })
}

// ---------------------------------------------------------------------------
// Block parsing
// ---------------------------------------------------------------------------

function isTableLine(line: string): boolean {
  return line.startsWith('|') && line.endsWith('|')
}

function splitTableRow(line: string): string[] {
  return line
    .slice(1, -1)
    .split('|')
    .map((cell) => cell.trim())
}

export function renderLegalMarkdown(markdown: string): ReactNode[] {
  const lines = markdown.split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i].trim()

    if (line === '') {
      i += 1
      continue
    }

    if (line.startsWith('### ')) {
      blocks.push(<h3 key={key++}>{renderInline(line.slice(4), `h3-${key}`)}</h3>)
      i += 1
      continue
    }
    if (line.startsWith('## ')) {
      blocks.push(<h2 key={key++}>{renderInline(line.slice(3), `h2-${key}`)}</h2>)
      i += 1
      continue
    }
    if (line.startsWith('# ')) {
      blocks.push(<h1 key={key++}>{renderInline(line.slice(2), `h1-${key}`)}</h1>)
      i += 1
      continue
    }

    if (line.startsWith('- ')) {
      const items: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('- ')) {
        items.push(lines[i].trim().slice(2))
        i += 1
      }
      blocks.push(
        <ul key={key++}>
          {items.map((item, j) => (
            <li key={j}>{renderInline(item, `ul-${key}-${j}`)}</li>
          ))}
        </ul>,
      )
      continue
    }

    const ordered = /^(\d+)\.\s+(.*)$/.exec(line)
    if (ordered) {
      const start = Number(ordered[1])
      const items: string[] = []
      while (i < lines.length) {
        const m = /^(\d+)\.\s+(.*)$/.exec(lines[i].trim())
        if (!m) break
        items.push(m[2])
        i += 1
      }
      blocks.push(
        <ol key={key++} start={start}>
          {items.map((item, j) => (
            <li key={j}>{renderInline(item, `ol-${key}-${j}`)}</li>
          ))}
        </ol>,
      )
      continue
    }

    if (isTableLine(line)) {
      const rows: string[][] = []
      while (i < lines.length && isTableLine(lines[i].trim())) {
        rows.push(splitTableRow(lines[i].trim()))
        i += 1
      }
      // Row 1 is the header; row 2 is the |---| separator (dropped).
      const [header, ...rest] = rows
      const body = rest.filter((cells) => !cells.every((c) => /^-*$/.test(c)))
      blocks.push(
        <table key={key++}>
          <thead>
            <tr>
              {header.map((cell, j) => (
                <th key={j} scope="col">
                  {renderInline(cell, `th-${key}-${j}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((cells, r) => (
              <tr key={r}>
                {cells.map((cell, c) => (
                  <td key={c}>{renderInline(cell, `td-${key}-${r}-${c}`)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      )
      continue
    }

    // Paragraph — consume consecutive non-blank, non-structural lines.
    const para: string[] = []
    while (i < lines.length) {
      const t = lines[i].trim()
      if (
        t === '' ||
        t.startsWith('#') ||
        t.startsWith('- ') ||
        /^\d+\.\s/.test(t) ||
        isTableLine(t)
      ) {
        break
      }
      para.push(t)
      i += 1
    }
    blocks.push(<p key={key++}>{renderInline(para.join(' '), `p-${key}`)}</p>)
  }

  return blocks
}
