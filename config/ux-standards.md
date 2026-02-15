# Agent Fishbowl — UX Standards

> This checklist defines the minimum UX expectations for the product.
> The UX agent reviews against these standards. The tech lead may update this document as the product evolves.

## Product Context

Agent Fishbowl is an AI-curated tech news feed. Users visit to:
1. Browse curated articles from AI/ML sources
2. Watch the AI agent team build the product in real-time (activity feed)

The audience is technical (developers, AI enthusiasts). The experience should feel fast, clean, and information-dense — not cluttered or overly decorated.

---

## Standards

### 1. Navigation & Structure
- [ ] Clear navigation between the news feed and activity feed (fishbowl)
- [ ] Current page/section is visually indicated
- [ ] User can always get back to the home page in one click

### 2. Content Hierarchy
- [ ] Article titles are the most prominent element on cards
- [ ] Source and date are visible but secondary
- [ ] Categories/tags are scannable without reading every card
- [ ] Content is sorted meaningfully (recent first, or by relevance)

### 3. Loading States
- [ ] Data-loading states show a spinner, skeleton, or placeholder
- [ ] The page is usable within 2 seconds of navigation
- [ ] No layout shift when data loads (skeleton matches final layout)

### 4. Error States
- [ ] API failures show a user-friendly message (not raw JSON or stack trace)
- [ ] Failed states offer a retry action when possible
- [ ] Partial failures don't break the entire page

### 5. Empty States
- [ ] "No articles found" shows a helpful message (not a blank page)
- [ ] Category filters with no results explain the empty state
- [ ] Activity feed with no events shows an explanation

### 6. Responsive Design
- [ ] Layout works on mobile (320px+), tablet (768px+), and desktop (1024px+)
- [ ] Touch targets are at least 44x44px on mobile
- [ ] Text is readable without zooming on all screen sizes
- [ ] No horizontal scrolling on any viewport

### 7. Dark Mode
- [ ] All components render correctly in dark mode
- [ ] Sufficient contrast ratios in both modes (WCAG AA: 4.5:1 for text)
- [ ] No "flash of wrong theme" on page load
- [ ] Images and icons are visible in both modes

### 8. Accessibility
- [ ] Images have descriptive alt text
- [ ] Interactive elements are keyboard-accessible (Tab, Enter, Escape)
- [ ] Headings follow semantic hierarchy (h1 → h2 → h3, no skipping)
- [ ] Links have descriptive text (not "click here")
- [ ] Focus indicators are visible on interactive elements

### 9. Visual Consistency
- [ ] Spacing follows a consistent scale (e.g., Tailwind's default spacing)
- [ ] Typography uses a consistent type scale
- [ ] Colors are from a defined palette (not ad-hoc hex values)
- [ ] Borders, shadows, and rounded corners are consistent across components

### 10. Interaction Feedback
- [ ] Buttons and links have hover/active states
- [ ] Clickable areas are obvious (cursor changes, visual affordance)
- [ ] Transitions are smooth (no jarring layout changes)
- [ ] External links are distinguishable from internal navigation
