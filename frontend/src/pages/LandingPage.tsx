import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useJoinWaitlist } from '../hooks/useWaitlist'
import signalReport from '../assets/animation-screen.jpg'
import './LandingPage.css'

/**
 * Public marketing landing page (ORPHEUS-8).
 *
 * Served on the www / apex host by the hostname branch in App.tsx; the product
 * app stays on app.orpheussocial.com. Single scrolling page: hero → about →
 * how it works → pricing (closed-beta framing) → waitlist capture. JS is only
 * used for the waitlist form; everything else is static, styled from the shared
 * design system (orpheus-styles.css).
 */

const APP_LOGIN_URL = 'https://app.orpheussocial.com/login'

const DIMENSIONS: { name: string; blurb: string }[] = [
  {
    name: 'Profile Clarity',
    blurb:
      'Does your profile give a clear, accurate read of who you are and what you do?',
  },
  {
    name: 'Signal Strength',
    blurb:
      'Have you built enough recent, consistent activity to register at all?',
  },
  {
    name: 'Signal Quality',
    blurb:
      'Are you doing the kinds of things that actually carry weight, not just noise?',
  },
  {
    name: 'Alignment',
    blurb:
      'Does what you post line up with the professional identity your profile claims?',
  },
]

const STEPS: { title: string; body: string }[] = [
  {
    title: 'Groundwork',
    body: 'Answer a short questionnaire and share an export of your LinkedIn profile. That is everything we need to begin.',
  },
  {
    title: 'Your Report',
    body: 'We measure how your professional presence is being interpreted across four dimensions — a precise picture of where you stand.',
  },
  {
    title: 'Quick Reference Card',
    body: 'Your report becomes a prioritized, specific plan: the exact moves that make your presence reflect the credibility you have earned.',
  },
]

export function LandingPage() {
  return (
    <div className="landing">
      <LandingNav />

      <main className="landing-main">
        <Hero />
        <About />
        <HowItWorks />
        <Pricing />
        <Waitlist />
      </main>

      <LandingFooter />
    </div>
  )
}

function LandingNav() {
  return (
    <nav className="nav landing-nav">
      <div className="wordmark">
        <span className="wordmark-orpheus">Orpheus</span>
        <span className="wordmark-social">Social</span>
      </div>
      <div className="landing-nav-actions">
        <a className="landing-nav-signin" href={APP_LOGIN_URL}>
          Sign in
        </a>
        <a className="btn-primary" href="#waitlist">
          Express Interest
        </a>
      </div>
    </nav>
  )
}

function Hero() {
  return (
    <section className="landing-hero">
      <span className="section-eyebrow">Presence, authentically interpreted</span>
      <h1 className="landing-hero-title">
        <span className="landing-hero-title-lead">Experience Speaks</span>
        <br />
        Make Yours <em>Sing</em>
      </h1>
      <p className="landing-hero-sub">
        Orpheus Social understands how your online presence is interpreted
        and shows you exactly how to make it resonate. Not vanity metrics or
        vague analytics. A clear diagnostic and a plan.
      </p>
      <div className="landing-hero-actions">
        <a className="btn-primary" href="#waitlist">
          Express Interest
        </a>
        <a className="btn-secondary" href="#about">
          See how it works
        </a>
      </div>

      <HeroAnimation />
    </section>
  )
}

/**
 * 3D signal-screen animation — faithful port of the Claude Design source
 * (Signal Hero). Geometry, colors, the on-screen report screenshot, and the
 * motion curve all mirror the original; the only change is the driver.
 *
 * The source scrubbed a 340vh scroll track (progress 0→1). Dropping that into
 * the bottom of the hero would hijack the whole page's scroll, so instead we
 * derive the same 0→1 progress from the element's own transit through the
 * viewport (its center travels from the bottom of the screen to the top): the
 * panel rotates in from +RANGE°, dwells centered through the HOLD window (glow
 * at full strength) as it crosses mid-screen, then rotates out to −RANGE°,
 * while the report screenshot scrolls top→bottom — exactly the source's
 * update() math, just driven by scroll position rather than a scroll track.
 *
 * Honors prefers-reduced-motion: the panel is pinned centered and the scroll
 * listener never attaches.
 */
function HeroAnimation() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const laptopRef = useRef<HTMLDivElement>(null)
  const glowRef = useRef<HTMLDivElement>(null)
  const ambientRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const wrap = wrapRef.current
    const stage = stageRef.current
    const laptop = laptopRef.current
    const glow = glowRef.current
    const ambient = ambientRef.current
    const img = imgRef.current
    if (!wrap || !laptop) return

    // Source motion constants (data-props defaults): rotationDeg 50,
    // holdFraction 0.34, glowIntensity 1.
    const RANGE = 50
    const HOLD = 0.2
    const clamp = (v: number, a: number, b: number) =>
      Math.min(b, Math.max(a, v))
    // Quintic smootherstep — zero 1st AND 2nd derivative at both ends, so
    // every transition (start, settle-in, settle-out, stop) eases with no
    // visible kink at the joins.
    const ease = (x: number) => {
      x = clamp(x, 0, 1)
      return x * x * x * (x * (x * 6 - 15) + 10)
    }

    // Render one frame at scroll-progress p (0→1), applying the source's
    // exact update() curve.
    const render = (p: number) => {
      const a0 = 0.5 - HOLD / 2
      const a1 = 0.5 + HOLD / 2
      let angle: number
      if (p < a0) angle = RANGE * (1 - ease(p / a0))
      else if (p > a1) angle = -RANGE * ease((p - a1) / (1 - a1))
      else angle = 0
      const c = 1 - Math.abs(angle) / RANGE
      const scale = 0.9 + c * 0.16
      const tilt = 5 - c * 2
      // Small symmetric drift centered on 0 (source used 96→56, which shoved
      // the panel out of its box here). Gentle rise as it settles centered.
      const ty = 14 - c * 28
      laptop.style.transform = `translateY(${ty}px) rotateX(${tilt}deg) rotateY(${angle}deg) scale(${scale})`
      const frac = ease(p)
      // Soft flat gradient — the ambient body of the glow.
      if (glow) glow.style.opacity = String(0.28 + 0.28 * c)
      // Ambient backlight: a blurred copy of the report, scrolled in sync so
      // the glow color reflects whatever region is on screen.
      if (ambient) {
        ambient.style.opacity = String(0.34 + 0.28 * c)
        ambient.style.backgroundPositionY = `${frac * 100}%`
      }
      if (img && img.offsetHeight) {
        const parent = img.parentElement
        const maxScroll = img.offsetHeight - (parent ? parent.clientHeight : 0)
        if (maxScroll > 0) img.style.transform = `translateY(${-maxScroll * frac}px)`
      }
    }

    // Size the panel to ~90% of the parent's width. The panel's intrinsic
    // width is 536px, so the stage scale that yields 0.9 × parent is
    // (0.9 × parentWidth) / 536, clamped to sane bounds.
    const PANEL_W = 536
    const layout = () => {
      if (!stage) return
      const w = wrap.clientWidth || PANEL_W
      const s = clamp((0.9 * w) / PANEL_W, 0.4, 1.6)
      stage.style.transform = `scale(${s})`
    }

    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      layout()
      render(0.5) // pinned centered, no motion
      return
    }

    // Scroll-linked, but driven by a fixed pixel distance from the top of the
    // page rather than the element's viewport-relative position — so the
    // animation always begins at p=0 (fully rotated in) at the top and
    // advances identically regardless of viewport height.
    const DISTANCE = 800
    let raf = 0
    const update = () => {
      raf = 0
      const y = window.scrollY || document.documentElement.scrollTop || 0
      const p = clamp(y / DISTANCE, 0, 1)
      render(p)
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    const onResize = () => {
      layout()
      onScroll()
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onResize)
    if (img && !img.complete)
      img.addEventListener('load', onScroll, { once: true })
    layout()
    update()
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onResize)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <div className="hero-anim" ref={wrapRef} aria-hidden="true">
      <div className="hero-anim-glow" ref={glowRef} />
      <div
        className="hero-anim-ambient"
        ref={ambientRef}
        style={{ backgroundImage: `url(${signalReport})` }}
      />
      <div className="hero-anim-stage" ref={stageRef}>
        <div className="hero-laptop" ref={laptopRef}>
          <div className="hero-screen-panel">
            <div className="hero-screen-back" />
            <div className="hero-screen-edge hero-screen-edge-l" />
            <div className="hero-screen-edge hero-screen-edge-r" />
            <div className="hero-screen-edge hero-screen-edge-t" />
            <div className="hero-screen-edge hero-screen-edge-b" />
            <div className="hero-screen-front">
              <span className="hero-screen-cam" />
              <div className="hero-screen-window">
                <img
                  ref={imgRef}
                  className="hero-screen-img"
                  src={signalReport}
                  alt=""
                />
              </div>
              <div className="hero-screen-gloss" />
              <span className="hero-screen-brand">Orpheus</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function About() {
  return (
    <section className="landing-section" id="about">
      <div className="section-header">
        <span className="section-eyebrow">What it is</span>
        <h2 className="section-title">
          A diagnostic for how you come across
        </h2>
      </div>
      <p className="landing-body">
        Your online presence is constantly being read by the systems that
        decide what to surface and by the people those systems reach. Orpheus Social
        analyzes your profile and activity and tells you how strong and coherent
        your presence is, on a scale from <em>dissonant</em> to{' '}
        <em>resonant</em>. Then it hands you a specific plan to help match your goals
        with the patterns and behaviors that drive resonance.
      </p>
      <div className="landing-dimensions">
        {DIMENSIONS.map((d) => (
          <div className="landing-dimension" key={d.name}>
            <div className="landing-dimension-name">{d.name}</div>
            <p className="landing-dimension-blurb">{d.blurb}</p>
          </div>
        ))}
      </div>
      <p className="landing-fineprint">
        Orpheus Social is a diagnostic and a coaching tool designed to help you take
        meaningful action to improve your overall online presence. Outcomes will vary
        based on your goals, your current presence, and the effort you put in.
      </p>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="landing-section" id="how">
      <div className="section-header">
        <span className="section-eyebrow">How it works</span>
        <h2 className="section-title">Three steps, one clear picture</h2>
      </div>
      <div className="landing-steps">
        {STEPS.map((s, i) => (
          <div className="landing-step" key={s.title}>
            <div className="landing-step-num">{i + 1}</div>
            <div className="landing-step-title">{s.title}</div>
            <p className="landing-step-body">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function Pricing() {
  return (
    <section className="landing-section" id="pricing">
      <div className="section-header">
        <span className="section-eyebrow">Pricing</span>
        <h2 className="section-title">Currently in closed beta</h2>
      </div>
      <div className="landing-pricing-cards">
        <div className="landing-pricing-card">
          <span className="landing-pricing-tag">Invitation only</span>
          <p className="landing-pricing-lead">Closed Beta</p>
          <p className="landing-pricing-body">
            We are onboarding a small group of members and refining the
            experience with them directly. Plans and pricing will be announced
            as we open up more broadly — join the waitlist and we will reach out
            with an invitation and early details.
          </p>
        </div>

        <div className="landing-pricing-card">
          <span className="landing-pricing-tag">Pre-release · 4 weeks</span>
          <p className="landing-pricing-lead">Live Workshop</p>
          <p className="landing-pricing-body">
            A four-week live program for a small group of individuals with
            similar backgrounds, looking for personal, hands-on guidance to
            improve their online presence together. Currently pre-release —
            express your interest and we will share the details as it takes
            shape.
          </p>
        </div>
      </div>
    </section>
  )
}

function Waitlist() {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [betaAccess, setBetaAccess] = useState(false)
  const [liveWorkshop, setLiveWorkshop] = useState(false)
  const [touched, setTouched] = useState(false)
  const mutation = useJoinWaitlist()

  const firstValid = firstName.trim().length > 0
  const lastValid = lastName.trim().length > 0
  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())
  const interests = [
    ...(betaAccess ? ['beta_access'] : []),
    ...(liveWorkshop ? ['live_workshop'] : []),
  ]
  const interestValid = interests.length > 0
  const formValid = firstValid && lastValid && emailValid && interestValid

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (!formValid) return
    mutation.mutate({
      firstName: firstName.trim(),
      lastName: lastName.trim(),
      email: email.trim(),
      interests,
    })
  }

  return (
    <section className="landing-section landing-waitlist" id="waitlist">
      <div className="section-header">
        <span className="section-eyebrow">Get early access</span>
        <h2 className="section-title">Express Interest</h2>
      </div>

      {mutation.isSuccess ? (
        <div className="landing-waitlist-success" role="status">
          <p className="landing-waitlist-success-title">Thanks, {firstName.trim()}.</p>
          <p className="landing-waitlist-success-body">
            You&rsquo;re on the list — we&rsquo;ll be in touch at{' '}
            <strong>{mutation.data.email}</strong> with next steps.
          </p>
        </div>
      ) : (
        <form className="landing-waitlist-form" onSubmit={onSubmit} noValidate>
          <div className="landing-waitlist-names">
            <div className="landing-waitlist-field">
              <label
                className="landing-waitlist-label"
                htmlFor="waitlist-first-name"
              >
                First Name
              </label>
              <input
                id="waitlist-first-name"
                className="landing-waitlist-input"
                type="text"
                autoComplete="given-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                aria-invalid={touched && !firstValid}
                disabled={mutation.isPending}
              />
            </div>
            <div className="landing-waitlist-field">
              <label
                className="landing-waitlist-label"
                htmlFor="waitlist-last-name"
              >
                Last Name
              </label>
              <input
                id="waitlist-last-name"
                className="landing-waitlist-input"
                type="text"
                autoComplete="family-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                aria-invalid={touched && !lastValid}
                disabled={mutation.isPending}
              />
            </div>
          </div>

          <div className="landing-waitlist-field">
            <label className="landing-waitlist-label" htmlFor="waitlist-email">
              Email Address
            </label>
            <input
              id="waitlist-email"
              className="landing-waitlist-input"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={touched && !emailValid}
              disabled={mutation.isPending}
            />
          </div>

          <fieldset className="landing-waitlist-interest">
            <legend className="landing-waitlist-label">
              I&rsquo;m interested in
            </legend>
            <label className="landing-checkbox">
              <input
                type="checkbox"
                checked={betaAccess}
                onChange={(e) => setBetaAccess(e.target.checked)}
                disabled={mutation.isPending}
              />
              <span>Beta Access</span>
            </label>
            <label className="landing-checkbox">
              <input
                type="checkbox"
                checked={liveWorkshop}
                onChange={(e) => setLiveWorkshop(e.target.checked)}
                disabled={mutation.isPending}
              />
              <span>Live Workshop</span>
            </label>
          </fieldset>

          {touched && !formValid && (
            <p className="landing-waitlist-error" role="alert">
              {!firstValid || !lastValid
                ? 'Please enter your first and last name.'
                : !emailValid
                  ? 'Please enter a valid email address.'
                  : 'Please select at least one interest.'}
            </p>
          )}
          {mutation.isError && (
            <p className="landing-waitlist-error" role="alert">
              Something went wrong. Please try again.
            </p>
          )}

          <button
            type="submit"
            className="btn-primary landing-waitlist-submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Submitting…' : 'Express Interest'}
          </button>

          <p className="landing-waitlist-note">
            We&rsquo;ll only use your details to contact you about Orpheus
            Social.
          </p>
        </form>
      )}
    </section>
  )
}

function LandingFooter() {
  return (
    <footer className="footer landing-footer">
      <div className="wordmark-sm">
        <span className="wordmark-sm-orpheus">Orpheus</span>
        <span className="wordmark-sm-social">Social</span>
      </div>
      <div className="footer-links">
        <a href={APP_LOGIN_URL}>Sign in</a>
        <a href="#">Terms of Service</a>
        <a href="#">Confidentiality</a>
        <span>Copyright &copy; 2026 All Rights Reserved.</span>
      </div>
    </footer>
  )
}
