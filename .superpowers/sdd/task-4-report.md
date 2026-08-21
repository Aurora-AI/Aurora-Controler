# Task 4: Fix RankingDeLojas Color Logic

## Problem
The red color for "negative margin" was being applied even when `has_sufficient_history` was `false` (cold-start store with insufficient data). This violated the project rule that "insufficient data should never become a visual fact".

## Root Cause
In `src/components/sections/RankingDeLojas.tsx`, line 45, the color decision was:
```tsx
className={`text-xs ${s.performance && s.performance.contribution_margin_total < 0 ? 'text-accent-red' : 'text-muted'}`}
```

This applied red color whenever `contribution_margin_total < 0`, regardless of data sufficiency. The only visual differentiation was the "(dado insuficiente)" text at the end of the line, which is easy to miss.

## Solution
Updated the condition to require BOTH:
1. `contribution_margin_total < 0` AND  
2. `has_sufficient_history === true`

New logic:
```tsx
className={`text-xs ${s.performance && s.performance.contribution_margin_total < 0 && s.performance.has_sufficient_history ? 'text-accent-red' : 'text-muted'}`}
```

When `has_sufficient_history` is `false`, the margin text now uses `text-muted` (neutral color), even if the margin is negative. This ensures uncertainty is visually encoded in the color, not just in supplemental text.

## Verification
- Type-check: `npx tsc --noEmit` ✓ (0 errors)
- Commit: `37f4275` - "fix(insight-board): cor de margem negativa respeita has_sufficient_history"
- Files modified: `src/components/sections/RankingDeLojas.tsx`

## Impact
This fix ensures that the visual encoding respects data quality — cold-start stores with uncertain margins no longer display the "red alert" color that would incorrectly suggest a confirmed business problem.
