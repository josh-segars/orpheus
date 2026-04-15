import { useState } from 'react'
import { SignalMeter, bandForScore } from '../../components/signal-meter'
import './SignalMeterPlayground.css'

/**
 * Dev-only playground for the SignalMeter component. Renders the meter at
 * multiple viewport widths simultaneously so responsive behavior is easy
 * to eyeball without resizing the browser. A score slider drives the
 * reticle position across all widths.
 */
export function SignalMeterPlayground() {
  const [score, setScore] = useState(58)
  const [widths, setWidths] = useState<number[]>([375, 768, 1024, 1440])

  const presets: { label: string; score: number }[] = [
    { label: 'Weak (12)', score: 12 },
    { label: 'Emerging (34)', score: 34 },
    { label: 'Moderate (58)', score: 58 },
    { label: 'Strong (72)', score: 72 },
    { label: 'Exceptional (90)', score: 90 },
    { label: 'Boundary 25', score: 25 },
    { label: 'Boundary 65', score: 65 },
  ]

  const allWidths = [375, 768, 1024, 1440]
  const toggleWidth = (w: number) => {
    setWidths((prev) =>
      prev.includes(w) ? prev.filter((x) => x !== w) : [...prev, w].sort((a, b) => a - b),
    )
  }

  const currentBand = bandForScore(score)

  return (
    <div className="smp-root">
      <header className="smp-header">
        <h1 className="smp-title">Signal Meter — Responsive Playground</h1>
        <p className="smp-subtitle">
          Drag the score slider to see the reticle move across the scale.
          Frame widths on the right simulate breakpoints — below 520px the
          active-band label stays prominent while inactive labels collapse.
        </p>
      </header>

      <div className="smp-controls">
        <div className="smp-control" style={{ minWidth: 280 }}>
          <div className="smp-control-label">
            Score
            <span className="smp-control-readout" style={{ marginLeft: 12 }}>
              {score.toFixed(1)}
            </span>
            <span className="smp-control-band">{currentBand}</span>
          </div>
          <input
            className="smp-slider"
            type="range"
            min={0}
            max={100}
            step={0.5}
            value={score}
            onChange={(e) => setScore(parseFloat(e.target.value))}
          />
          <div className="smp-preset-row" style={{ marginTop: 6 }}>
            {presets.map((p) => (
              <button
                key={p.label}
                type="button"
                className="smp-preset"
                onClick={() => setScore(p.score)}
                aria-pressed={score === p.score}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="smp-control">
          <div className="smp-control-label">Widths shown</div>
          <div className="smp-preset-row">
            {allWidths.map((w) => (
              <button
                key={w}
                type="button"
                className="smp-preset"
                onClick={() => toggleWidth(w)}
                aria-pressed={widths.includes(w)}
              >
                {w}px
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="smp-frames">
        {widths.map((w) => (
          <div key={w} className="smp-frame" style={{ maxWidth: w }}>
            <div className="smp-frame-label">
              <span>
                Viewport <code>{w}px</code>
              </span>
              <span>
                container-width <code>{w - 40}px</code>
              </span>
            </div>
            <div className="smp-frame-body">
              <SignalMeter score={score} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
