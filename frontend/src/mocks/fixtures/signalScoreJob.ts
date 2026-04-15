import type { Job } from '../../types/job'

/**
 * Illustrative completed-job fixture in the v2 4-dimension shape.
 * Composite = 58.0 → "Moderate" band (45–64). Sits cleanly inside the band
 * rather than on the Moderate/Strong boundary.
 * Sub-dimension scores are plausible but synthetic.
 */
export const demoJob: Job = {
  id: 'demo',
  state: 'complete',
  created_at: '2026-04-12T14:03:00Z',
  updated_at: '2026-04-12T14:04:18Z',
  client_id: 'jane-doe',
  error: null,
  result: {
    scoring: {
      scored_dimensions: {
        composite: 58.0,
        band: 'Moderate',
        dimensions: [
          {
            name: 'Profile Signal Clarity',
            weight: 0.35,
            confidence: 'CONFIRMED',
            normalized_score: 0.72,
            contribution: 25.2,
            completeness_floor_applied: false,
            sub_dimensions: [
              {
                name: 'Headline specificity',
                score: 4,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'Your headline identifies you by role and focus without relying on a generic title, giving the retrieval system a clear signal of where to place you. Adding a strategic qualifier — who you serve, or what you change — would tighten the signal further.',
                best_practices:
                  'A strong headline resolves in a single phrase: who you are, who you help, and the category you own. Stacked roles separated by pipes dilute the signal; the retrieval model treats the first phrase as the anchor.',
                improvements: [
                  'Add one concrete qualifier (industry, client type, or outcome) to your current headline.',
                  'Replace role abbreviations with full terms so keyword matching catches them.',
                ],
              },
              {
                name: 'About-section substance',
                score: 4,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'The first 300 characters of your About section carry most of the retrieval weight. Your opening paragraph is specific and audience-facing — which is what this sub-dimension rewards — though the close drifts into general career history.',
                best_practices:
                  'The opening one or two sentences should read like a positioning statement: who, what, for whom. The rest of the section can narrate, but the opening carries the weight.',
                improvements: [
                  'Move your strongest client outcome into the first 100 characters.',
                  'End with a clear next-step line so interested readers know what to do.',
                ],
              },
              {
                name: 'Experience narrative',
                score: 3,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'Your Experience entries are well-organized but lean heavily on titles and scope. Outcome-led language — numbers, shifts, artifacts delivered — is present but sparse, which limits the model\u2019s ability to match you to specific intent queries from prospective clients.',
                best_practices:
                  'Each Experience entry should lead with a business outcome, not a responsibility. One quantified result per role is the minimum; two or three is the benchmark for senior profiles.',
                improvements: [
                  'Rewrite the first bullet of each role to start with an outcome verb (shifted, reduced, unlocked, shipped).',
                  'Add at least one quantified metric per role — revenue, team size, time-to-value, or count of outputs.',
                  'Remove duties-only bullets that don\u2019t describe what was produced or changed.',
                ],
              },
              {
                name: 'Skills coherence',
                score: 4,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'Your skills list is consistent with your Experience entries, and endorsement density is above the threshold the model treats as a proxy for relevance. Coherence here is a quiet strength.',
                best_practices:
                  'Keep the top five skills synchronized with your current focus. Pruning quarterly to remove anything that no longer represents your work keeps the signal clean.',
                improvements: [
                  'Add one or two skills that match the language your target clients use in their own role descriptions.',
                ],
              },
              {
                name: 'Recommendations social proof',
                score: 2,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'Two received recommendations is low for someone at your stage. This sub-dimension rewards third-party validation, and the gap between your current count and what senior professionals typically show is the most visible weakness in your profile.',
                best_practices:
                  'Senior profiles typically carry eight to fifteen recommendations. Recency matters as much as count; recommendations from the last twelve months carry more weight in ranking than older ones.',
                improvements: [
                  'Request a recommendation from a client who has seen a recent win.',
                  'Ask a peer or collaborator from the last year to write one.',
                  'Write a recommendation for someone first — reciprocity makes the ask easier.',
                ],
              },
            ],
          },
          {
            name: 'Behavioral Signal Strength',
            weight: 0.3,
            confidence: 'CONFIRMED',
            normalized_score: 0.55,
            contribution: 16.5,
            completeness_floor_applied: false,
            sub_dimensions: [
              {
                name: 'Volume',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 1.4,
                summary:
                  'At 1.4 posts per week you have a measurable cadence, but it sits below the threshold the ranking model treats as consistent publishing. Enough data exists for evaluation; not enough for momentum to compound.',
                best_practices:
                  'The retrieval system rewards steady activity. A minimum of two posts per week gives the model a regular signal to index; three or more puts you in the band where content begins compounding week over week.',
                improvements: [
                  'Commit to a fixed weekly cadence you can defend for 12 weeks — two posts minimum.',
                  'Batch-draft on one day so mid-week bandwidth constraints don\u2019t break the streak.',
                ],
              },
              {
                name: 'Recency',
                score: 3,
                scale: '0-5',
                method: 'quantitative_hybrid',
                confidence: 'CONFIRMED',
                raw_value: 0.71,
                summary:
                  '71% of weeks over the past year had outbound activity. Recent weeks are active, but enough gaps exist in the tail that the ranking model discounts older posts faster than it otherwise would.',
                best_practices:
                  'Recency compounds: recent posts carry higher ranking weight than older ones, and a rolling average of activity matters more than any single week\u2019s volume.',
                improvements: [
                  'Identify the last two multi-week gaps and note what interrupted activity; build a mitigation into your publishing plan.',
                  'Queue evergreen posts during known busy weeks so the stream doesn\u2019t go dark.',
                ],
              },
              {
                name: 'Coherence',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 0.48,
                summary:
                  'Activity is present, but fewer than half of your active weeks maintain a coherent rhythm. Burst publishing is visible — three posts in one week, then silence for two — which limits algorithmic momentum.',
                best_practices:
                  'Coherence is about predictability for the ranking model, not volume. One post per week, every week, outperforms three in one week followed by silence — even though the total is lower.',
                improvements: [
                  'Set a recurring calendar block for posting: same day, same window, every week.',
                  'Pre-publish a minimum viable post each week (short, pointed, no formatting fuss) rather than waiting for a \u201cbig\u201d post.',
                ],
              },
            ],
          },
          {
            name: 'Behavioral Signal Quality',
            weight: 0.2,
            confidence: 'CONFIRMED',
            normalized_score: 0.61,
            contribution: 12.2,
            completeness_floor_applied: false,
            sub_dimensions: [
              {
                name: 'Original content share',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 0.42,
                summary:
                  '42% of your outbound activity is original content; the remainder is reactions and comments on others\u2019 posts. The mix is skewed toward consumption signals rather than production signals.',
                best_practices:
                  'Original posts generate retrieval signals that reactions don\u2019t. The benchmark for senior voices is typically 60\u201370% original content by action count.',
                improvements: [
                  'Convert a thoughtful comment from the last quarter into a standalone post.',
                  'Allocate one slot per week to original commentary rather than reshares.',
                ],
              },
              {
                name: 'Comment depth',
                score: 4,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 28,
                summary:
                  'Your comments average 28 words \u2014 well above the substantive-engagement threshold and in the range the model treats as a quality signal rather than passive acknowledgment.',
                best_practices:
                  'Comments of 20+ words are treated as substantive engagement; under 20 reads as acknowledgment. Depth signals active participation in the conversation, which the ranking system rewards.',
                improvements: [
                  'Maintain the current depth \u2014 no change needed to preserve this signal.',
                ],
              },
              {
                name: 'Reaction mix',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary:
                  'Your reaction mix is balanced across the available types rather than skewed entirely toward \u201cLike.\u201d The retrieval model reads diverse reactions as more considered engagement than single-button behavior.',
                best_practices:
                  'The full reaction palette (Insightful, Celebrate, Support, etc.) is weighted more in algorithmic assessment than simple likes. Use the reaction that matches the content rather than defaulting.',
                improvements: [
                  'Lean into \u201cInsightful\u201d and \u201cCelebrate\u201d reactions where they fit \u2014 they carry more signal than generic likes.',
                ],
              },
            ],
          },
          {
            name: 'Profile-Behavior Alignment',
            weight: 0.15,
            confidence: 'INFERRED',
            normalized_score: 0.72,
            contribution: 10.8,
            completeness_floor_applied: false,
            sub_dimensions: [
              {
                name: 'Topical consistency',
                score: 4,
                scale: '1-5',
                method: 'rubric',
                confidence: 'INFERRED',
                raw_value: null,
                summary:
                  'Your content is topically consistent with the identity declared in your profile. The model places you in a coherent topic cluster without contradictions.',
                best_practices:
                  'A follower arriving from any single post should reach a profile that confirms rather than contradicts what they just read. Tight topical coherence compounds retrieval accuracy over time.',
                improvements: [
                  'Continue the current topic discipline \u2014 no changes needed here.',
                ],
              },
              {
                name: 'Voice consistency',
                score: 3,
                scale: '1-5',
                method: 'rubric',
                confidence: 'INFERRED',
                raw_value: null,
                summary:
                  'Voice varies across posts \u2014 some are formal and observation-led, others drift into casual commentary. The content is on-topic but the register isn\u2019t yet settled.',
                best_practices:
                  'A consistent voice is part of how readers (and the model) build a stable impression. Pick a register \u2014 analytical, narrative, direct \u2014 and hold it across posts.',
                improvements: [
                  'Before posting, scan recent entries and ask whether the draft\u2019s tone matches. If it doesn\u2019t, revise or hold.',
                  'Establish a short list of voice markers (sentence length, use of first person, formality) and check drafts against it.',
                ],
              },
            ],
          },
        ],
      },
      forward_brief_data: {
        quantitative: {
          follower_count: 1247,
          follower_growth_rate: 4.2,
          unique_members_reached: 18_340,
          avg_impressions_per_post: 780,
          avg_engagement_rate: 0.018,
          top_post_impressions: 7_240,
          audience_seniority: {
            Senior: 0.31,
            Director: 0.1,
            VP: 0.06,
          },
          audience_industries: [
            { name: 'Management Consulting', pct: 0.28 },
            { name: 'Financial Services', pct: 0.17 },
            { name: 'Technology', pct: 0.13 },
          ],
          audience_geography: [
            { name: 'DC-Baltimore', pct: 0.19 },
            { name: 'New York', pct: 0.14 },
            { name: 'San Francisco', pct: 0.08 },
          ],
          top_organizations: ['McKinsey', 'Deloitte', 'Harvard Business School'],
          avg_comment_length_words: 34,
          longest_posting_gap_weeks: 3,
          zero_post_week_pct: 0.29,
        },
        qualitative_flags: {
          viewer_actor_affinity: {
            concentrated: false,
            top_targets: [],
          },
          visual_professionalism: {
            photo_present: true,
          },
          engagement_invitation: {
            services_present: false,
            contact_visible: true,
            cta_in_about: false,
          },
        },
      },
    },
    narratives: {
      dimension_narratives: {
        'Profile Signal Clarity':
          'Your profile reads as substantive and credible. The headline and About section give the retrieval system enough specific language to place you accurately in an executive, strategy-oriented embedding space. Experience entries describe scope but lean toward titles and responsibilities rather than outcomes — this is the single largest opportunity inside this dimension. Skills and endorsements form a coherent picture. The recommendations count is the visible gap: two received recommendations is low for someone at your stage and limits third-party validation that the ranking model associates with authority signals.',
        'Behavioral Signal Strength':
          'You have posted enough over the past year that the model has data to work with, but publishing is sporadic rather than systematic. An average of 1.4 posts per week is in the functional range, though 29% of weeks had zero posts and the longest gap was three weeks — long enough that momentum resets between bursts. The retrieval system rewards steady, recent activity; closing the gaps is higher leverage than raising the peak.',
        'Behavioral Signal Quality':
          'Your activity mix skews toward the signals the optimization targets actually reward. Comments average 34 words, well above passive-engagement thresholds, and about 42% of your activity is original content rather than pure reshares. The mix is healthy. To raise this further, increase the proportion of original posts versus reactions without reducing comment depth.',
        'Profile-Behavior Alignment':
          'Content is topically consistent with the identity your profile declares — executive advisory, digital strategy, and adjacent themes. Voice is steady across posts. The alignment is strong enough that a new follower arriving from any single post would reach a profile that confirms rather than contradicts what they just read.',
      },
      forward_brief:
        '## Priorities\n\nThe fastest compound improvement comes from closing the consistency gap inside Behavioral Signal Strength. Pick a weekly cadence you will keep for 12 weeks and protect it as non-negotiable.\n\n## Quick Wins\n\n- Request two to three recommendations from senior colleagues this month.\n- Add one outcome-led sentence to each of your three most recent Experience entries.\n- Convert one long-form reply you wrote this quarter into a standalone post.',
    },
  },
}
