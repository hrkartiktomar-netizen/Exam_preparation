# Frontend Libraries Reference Manual (Sourced via Context7 MCP)

> **Authoritative Source:** Context7 MCP (`https://mcp.context7.com/mcp`)
> **Retrieved On:** 2026-08-31T20:11:41.445Z
> **Libraries Covered:** Lenis v1.x, GSAP v3 (with ScrollTrigger, SplitText, Flip, Observer, matchMedia), Three.js r185+

---

## Lenis — Lenis constructor options lerp duration easing smoothWheel syncTouch autoRaf autoResize autoToggle infinite

*Context7 Library ID:* `/darkroomengineering/lenis`

### new Lenis(options)

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Initializes a new Lenis instance with optional configuration settings.

```APIDOC
## new Lenis(options)

### Description
Initializes the Lenis smooth scrolling instance. This constructor accepts an object of settings to customize the scrolling behavior.

### Parameters
#### Options
- **allowNestedScroll** (boolean) - Optional - Automatically allow nested scrollable elements to scroll natively.
- **anchors** (boolean, ScrollToOptions) - Optional - Enable scrolling to anchor links when clicked.
- **autoRaf** (boolean) - Optional - Whether or not to automatically run requestAnimationFrame loop.
- **autoResize** (boolean) - Optional - Resize instance automatically based on ResizeObserver.
- **autoToggle** (boolean) - Optional - Automatically start or stop the lenis instance based on the wrapper's overflow property.
- **content** (HTMLElement) - Optional - The element that contains the content that will be scrolled.
- **duration** (number) - Optional - The duration of scroll animation in seconds.
- **easing** (function) - Optional - The easing function to use for the scroll animation.
- **eventsTarget** (HTMLElement, Window) - Optional - The element that will listen to wheel and touch events.

### Request Example
```javascript
new Lenis({
  autoRaf: true,
  autoToggle: true,
  anchors: true,
  allowNestedScroll: true
})
```
```

--------------------------------

### Animation engine: lerp vs duration paths

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/animate.ts

Core animation code showing the two mutually exclusive smooth-scroll modes. When `duration`+`easing` is set, animation is time-based with an easing curve. When `lerp` is set (default 0.1), frame-rate-independent damping via `damp()` is used. Only one path runs; if neither is configured, lerp defaults to 0.1. Picking the wrong mode for your use case causes janky or sluggish scroll.

```typescript
  advance(deltaTime: number) {
    if (!this.isRunning) return

    let completed = false

    if (this.duration && this.easing) {
      this.currentTime += deltaTime
      const linearProgress = clamp(0, this.currentTime / this.duration, 1)

      completed = linearProgress >= 1
      const easedProgress = completed ? 1 : this.easing(linearProgress)
      this.value = this.from + (this.to - this.from) * easedProgress
    } else if (this.lerp) {
      this.value = damp(this.value, this.to, this.lerp * 60, deltaTime)
      if (Math.round(this.value) === Math.round(this.to)) {
        this.value = this.to
        completed = true
      }
    } else {
      this.value = this.to
      completed = true
    }

    if (completed) {
      this.stop()
    }

    this.onUpdate?.(this.value, completed)
  }
```

--------------------------------

### LenisOptions with orientation, wrapper, content, infinite, and virtualScroll

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/types.ts

The full LenisOptions type showing how to configure horizontal orientation, custom wrapper/content elements, infinite scrolling, and the virtualScroll callback — all directly available from the constructor options.

```typescript
export type LenisOptions = {
  wrapper?: Window | HTMLElement | Element
  content?: HTMLElement | Element
  smoothWheel?: boolean
  syncTouch?: boolean
  infinite?: boolean
  orientation?: Orientation
  gestureOrientation?: GestureOrientation
  virtualScroll?: (data: VirtualScrollData) => boolean
  prevent?: (node: HTMLElement) => boolean
  // ... other options
}
```

--------------------------------

### Programmatic scrollTo shortest-path wrapping

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

When `infinite: true` and a programmatic `scrollTo` is called, this code disables the normal `clamp(0, target, limit)` and instead wraps the target by ±limit if the distance exceeds half the limit — taking the shorter path around the circular scroll space.

```typescript
if (this.options.infinite) {
  if (programmatic) {
    this.targetScroll = this.animatedScroll = this.scroll

    const distance = target - this.animatedScroll

    if (distance > this.limit / 2) {
      target -= this.limit
    } else if (distance < -this.limit / 2) {
      target += this.limit
    }
  }
} else {
  target = clamp(0, target, this.limit)
}
```

### Settings > duration and easing

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Scroll animation behavior is controlled by duration and easing parameters. The duration is measured in seconds, while the easing function determines the animation curve. Note that these settings are ignored if a lerp value is defined.

---

## Lenis — Lenis GSAP ScrollTrigger ticker integration raf lagSmoothing

*Context7 Library ID:* `/darkroomengineering/lenis`

### Integrate Lenis with GSAP ScrollTrigger

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Synchronize Lenis smooth scrolling with GSAP's ticker and ScrollTrigger plugin.

```js
// Initialize a new Lenis instance for smooth scrolling
const lenis = new Lenis();

// Synchronize Lenis scrolling with GSAP's ScrollTrigger plugin
lenis.on('scroll', ScrollTrigger.update);

// Add Lenis's requestAnimationFrame (raf) method to GSAP's ticker
// This ensures Lenis's smooth scroll animation updates on each GSAP tick
gsap.ticker.add((time) => {
  lenis.raf(time * 1000); // Convert time from seconds to milliseconds
});

// Disable lag smoothing in GSAP to prevent any delay in scroll animations
gsap.ticker.lagSmoothing(0);
```

--------------------------------

### raf(time)

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Updates the internal state of the Lenis instance. This method must be called every frame.

```APIDOC
## raf(time)

### Description
Updates the internal state of the Lenis instance. This method must be called every frame.

### Parameters
- **time** (number) - Required - The current time in milliseconds.
```

--------------------------------

### onUpdate inside scrollTo — the smooth scroll per-frame handler

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

This is the callback invoked by Animate.advance each frame. It sets isScrolling='smooth', updates animatedScroll, calls setScroll (which synchronously sets window.scrollY), and emits the Lenis scroll event. Every external window scroll listener attached by user code fires synchronously from setScroll, but onNativeScroll is a no-op because isScrolling is 'smooth', not 'false' or 'native'. Neither user-added window scroll listeners nor Lenis scroll listeners are intentionally delayed.

```typescript
      onUpdate: (value: number, completed: boolean) => {
        this.isScrolling = 'smooth'

        // updated
        this.lastVelocity = this.velocity
        this.velocity = value - this.animatedScroll
        this.direction = Math.sign(this.velocity) as Lenis['direction']

        this.animatedScroll = value
        this.setScroll(this.scroll)

        if (programmatic) {
          // wheel during programmatic should stop it
          this.targetScroll = value
        }

        if (!completed) this.emit()

        if (completed) {
          this.reset()
          this.emit()
          onComplete?.(this)
          this.userData = {}

          requestAnimationFrame(() => {
            this.dispatchScrollendEvent()
          })

          // avoid emitting event twice
          this.preventNextNativeScrollEvent()
        }
      },
```

### Setup > GSAP ScrollTrigger

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis integrates with GSAP ScrollTrigger by synchronizing scroll events and adding the Lenis requestAnimationFrame method to the GSAP ticker. Disabling GSAP lag smoothing is recommended to ensure smooth scroll animations.

--------------------------------

### lenis/vue > Examples > GSAP integration

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/vue/README.md

When integrating Lenis with GSAP, it's important to update GSAP's ScrollTrigger on Lenis scroll events. You should also add Lenis's `raf` method to GSAP's ticker to ensure smooth animation updates and disable GSAP's lag smoothing for immediate scroll animation responses.

---

## Lenis — Lenis scrollTo stop start destroy on scroll event listener

*Context7 Library ID:* `/darkroomengineering/lenis`

### Initialize Lenis with basic configuration

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Basic setup with autoRaf enabled and a scroll event listener.

```js
// Initialize Lenis
const lenis = new Lenis({
  autoRaf: true,
});

// Listen for the scroll event and log the event data
lenis.on('scroll', (e) => {
  console.log(e);
});
```

--------------------------------

### scrollTo(target, options)

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Programmatically scrolls to a specified target with configurable animation options.

```APIDOC
## scrollTo(target, options)

### Description
Scrolls to a specific target. The target can be a pixel value, a CSS selector, a keyword, or an HTMLElement.

### Parameters
- **target** (number|string|HTMLElement) - Required - The goal to reach.
- **options** (object) - Optional - Configuration for the scroll animation:
  - **offset** (number): Equivalent to scroll-padding-top.
  - **lerp** (number): Animation lerp intensity.
  - **duration** (number): Animation duration in seconds.
  - **easing** (function): Animation easing function.
  - **immediate** (boolean): If true, ignores duration, easing, and lerp.
  - **lock** (boolean): Prevents user scrolling until target is reached.
  - **force** (boolean): Reaches target even if instance is stopped.
  - **onComplete** (function): Callback executed when target is reached.
  - **userData** (object): Data forwarded through scroll events.
```

--------------------------------

### lenis.stop()

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Pauses the scroll behavior of the Lenis instance.

```APIDOC
## stop()

### Description
Pauses the scroll behavior of the Lenis instance.

### Usage
```javascript
lenis.stop();
```
```

--------------------------------

### start()

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Resumes the scroll functionality.

```APIDOC
## start()

### Description
Resumes the scroll functionality.
```

--------------------------------

### destroy()

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

The destroy method is used to clean up the Lenis instance by removing all associated events.

```APIDOC
## destroy()

### Description
Destroys the instance and removes all events.

### Signature
`destroy()`
```

---

## Lenis — Lenis prefers-reduced-motion accessibility virtualScroll

*Context7 Library ID:* `/darkroomengineering/lenis`

### Disable Reduced Motion Respect

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Override the default behavior of honoring the prefers-reduced-motion media query by setting respectReducedMotion to false.

```js
const lenis = new Lenis({
  respectReducedMotion: false,
})
```

--------------------------------

### Lenis Configuration Settings

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Configuration options available when initializing a Lenis instance to manage scroll behavior and event handling.

```APIDOC
## Lenis Configuration Settings

### Settings
- **touchInertiaExponent** (number) - Default: 1.7 - Manage the strength of syncTouch inertia.
- **touchMultiplier** (number) - Default: 1 - The multiplier to use for touch events.
- **virtualScroll** (function) - Default: undefined - Manually modify the events before they get consumed. If false is returned, the scroll will not be smoothed.
- **wheelMultiplier** (number) - Default: 1 - The multiplier to use for mouse wheel events.
- **wrapper** (HTMLElement, Window) - Default: window - The element that will be used as the scroll container.
```

--------------------------------

### Modify virtual scroll events

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Use the virtualScroll function to intercept and modify scroll events before they are processed by Lenis.

```javascript
(e) => { e.deltaY /= 2 }
```

```javascript
({ event }) => !event.shiftKey
```

--------------------------------

### Custom virtualScroll callback runs first, before all other processing

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

The `options.virtualScroll` callback is invoked at the very top of `onVirtualScroll`. If it returns `false`, the method returns immediately — before any prevent filtering, stopped/locked checks, or touch/wheel classification.

```typescript
private onVirtualScroll = (data: VirtualScrollData) => {
    if (
      typeof this.options.virtualScroll === 'function' &&
      this.options.virtualScroll(data) === false
    )
      return

    const { deltaX, deltaY, event } = data

    this.emitter.emit('virtual-scroll', { deltaX, deltaY, event })

    // keep zoom feature
    if (event.ctrlKey) return
    // @ts-expect-error
    if (event.lenisStopPropagation) return

    const isTouch = event.type.includes('touch')
    const isWheel = event.type.includes('wheel')
```

### Considerations > Reduced motion

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis automatically respects the user's prefers-reduced-motion system setting. When reduced motion is enabled, smoothing is disabled and programmatic scrolls jump instantly to their target, though the library continues to run to maintain synchronization. Developers can opt out of this behavior by setting respectReducedMotion to false, or check the lenis.prefersReducedMotion property to adjust their own animations accordingly.

---

## GSAP Core — GSAP defaults to from fromTo timeline set ticker lagSmoothing

*Context7 Library ID:* `/greensock/gsap-skills`

### Set Timeline Defaults

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

Pass a `defaults` object to the `gsap.timeline()` constructor to apply common properties like `duration` and `ease` to all child tweens automatically.

```javascript
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power2.out" } });
tl.to(".a", { x: 100 }).to(".b", { y: 50 }); // both use 0.5s and power2.out
```

--------------------------------

### GSAP Timelines for Sequencing Animations

Source: https://context7.com/greensock/gsap-skills/llms.txt

Use gsap.timeline() to sequence multiple tweens with precise control using the position parameter, labels, and defaults. Timelines support the same playback API as tweens and are preferred over chaining with delay.

```javascript
import { gsap } from "gsap";

// Basic sequence with position parameter
const tl = gsap.timeline({
  defaults: { duration: 0.5, ease: "power2.out" },
  repeat: 0,
  onComplete: () => console.log("sequence complete")
});

tl.from(".title",   { y: 40, autoAlpha: 0 })
  .from(".subtitle",{ y: 30, autoAlpha: 0 }, "-=0.2") // 0.2s overlap with previous
  .from(".cta",     { scale: 0.8, autoAlpha: 0 }, "+=0.1") // 0.1s gap
  .to(".bg",        { backgroundColor: "#1a1a2e" }, 0); // absolute: starts at t=0
```

```javascript
// Labels for readable sequencing
tl.addLabel("reveal", 0.5);
tl.from(".card", { y: 20, autoAlpha: 0, stagger: 0.1 }, "reveal");
tl.from(".icon", { scale: 0 }, "reveal+=0.2");
```

```javascript
// Nesting timelines
const childTl = gsap.timeline();
childTl.to(".a", { x: 100 }).to(".b", { y: 50 });

const masterTl = gsap.timeline();
masterTl.add(childTl, 0).to(".c", { autoAlpha: 0 }, "+=0.2");
```

```javascript
// Playback control
tl.pause();
tl.play("reveal");      // play from a label
tl.tweenFromTo("reveal", "outro"); // animate between two labels
tl.progress(0.5);
tl.kill();
```

--------------------------------

### Set GSAP Defaults

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-core/SKILL.md

Configure project-wide default tween properties using gsap.defaults(). This is useful for maintaining consistent animation settings across your application.

```javascript
gsap.defaults({ duration: 0.6, ease: "power2.out" });
```

### GSAP Timeline > Timeline Options (constructor)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

When creating a GSAP timeline, you can pass various options to the constructor. These include 'paused: true' to create a paused timeline, 'repeat' and 'yoyo' for repeating animations, timeline-level callbacks like 'onComplete' and 'onStart', and 'defaults' to set default properties for child tweens.

--------------------------------

### GSAP Timeline > Timeline Defaults

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

Timeline defaults can be passed into the constructor, allowing all child tweens to inherit properties like duration and ease. This is useful when many tweens share the same settings.

---

## GSAP matchMedia — gsap.matchMedia add conditions desktop mobile reducedMotion revert cleanup

*Context7 Library ID:* `/greensock/gsap-skills`

### GSAP Defaults and Responsive Animations with matchMedia

Source: https://context7.com/greensock/gsap-skills/llms.txt

Set project-wide Tween defaults using gsap.defaults(). Use gsap.matchMedia() to scope animations to media query conditions and automatically revert them, ideal for responsive design and accessibility.

```javascript
import { gsap } from "gsap";

// Project-wide defaults
gsap.defaults({ duration: 0.6, ease: "power2.out" });
```

```javascript
// Responsive + reduced-motion accessible animations
const mm = gsap.matchMedia();

mm.add(
  {
    isDesktop: "(min-width: 800px)",
    isMobile:  "(max-width: 799px)",
    reduceMotion: "(prefers-reduced-motion: reduce)"
  },
  (context) => {
    const { isDesktop, reduceMotion } = context.conditions;

    gsap.to(".hero", {
      x: isDesktop ? 200 : 50,
      duration: reduceMotion ? 0 : 0.8  // skip animation if user prefers it
    });

    // Optional custom cleanup when conditions no longer match
    return () => console.log("conditions changed, reverted");
  }
);
```

```javascript
// Revert all matchMedia animations (e.g. on component unmount)
mm.revert();
```

--------------------------------

### Responsive Animations with GSAP matchMedia

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-core/SKILL.md

Implement responsive design and accessibility features using gsap.matchMedia(). It runs setup code only when media queries match and automatically reverts animations when they stop matching.

```javascript
let mm = gsap.matchMedia();
mm.add(
  {
    isDesktop: "(min-width: 800px)",
    isMobile: "(max-width: 799px)",
    reduceMotion: "(prefers-reduced-motion: reduce)"
  },
  (context) => {
    const { isDesktop, reduceMotion } = context.conditions;
    gsap.to(".box", {
      rotation: isDesktop ? 360 : 180,
      duration: reduceMotion ? 0 : 2  // skip animation when user prefers reduced motion
    });
    return () => { /* optional cleanup when no condition matches */ };
  }
);
```

### Defaults and gsap.matchMedia()

Source: https://context7.com/greensock/gsap-skills/llms.txt

gsap.defaults() sets project-wide Tween defaults. gsap.matchMedia() (GSAP 3.11+) scopes animations to media query conditions and automatically reverts them when conditions no longer match, which is the correct pattern for responsive animations and prefers-reduced-motion accessibility.

--------------------------------

### Accessibility and responsive (gsap.matchMedia())

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-core/SKILL.md

gsap.matchMedia() is a powerful tool for creating responsive animations and handling accessibility. It runs setup code only when specific media queries match and automatically reverts animations and ScrollTriggers when the conditions are no longer met. This is crucial for adapting animations to different screen sizes and for respecting user preferences like 'prefers-reduced-motion'.

--------------------------------

### Accessibility and responsive (gsap.matchMedia())

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-core/SKILL.md

When using multiple named queries with gsap.matchMedia(), you can pass an object to the `add` method. The handler function receives a context object containing `context.conditions`, which are booleans indicating which named queries are currently active. This allows for conditional animation logic based on multiple breakpoints or preferences.

---

## GSAP ScrollTrigger — ScrollTrigger create defaults trigger start end scrub pin pinSpacing refresh kill update

*Context7 Library ID:* `/greensock/gsap-skills`

### ScrollTrigger: Scrubbed Pinned Section with Timeline

Source: https://context7.com/greensock/gsap-skills/llms.txt

Ideal for creating immersive scrolling experiences where animations sync with scroll progress and sections remain pinned. Configure `scrub` for lag and `pin` to hold the element.

```javascript
// Scrubbed pinned section — timeline progress matches scroll position
const pinTl = gsap.timeline({
  scrollTrigger: {
    trigger: ".section",
    start: "top top",
    end: "+=2000",
    scrub: 1,         // 1s lag; use true for direct link
    pin: true,        // pin .section while active
    pinSpacing: true, // default; add spacer to prevent layout collapse
    markers: false    // set true during dev
  }
});
pinTl
  .to(".layer-1", { xPercent: -20 })
  .to(".layer-2", { xPercent: -40 }, "<"
  .from(".text",  { autoAlpha: 0, y: 30 });
```

--------------------------------

### ScrollTrigger: Refresh and Cleanup

Source: https://context7.com/greensock/gsap-skills/llms.txt

Manually refresh ScrollTriggers after layout changes to update positions and dimensions. Use `ScrollTrigger.getAll().forEach(t => t.kill())` to remove all ScrollTriggers.

```javascript
// Refresh after layout changes; kill all on teardown
ScrollTrigger.refresh();
ScrollTrigger.getAll().forEach(t => t.kill());
```

--------------------------------

### ScrollTrigger: Standalone Trigger with Callback

Source: https://context7.com/greensock/gsap-skills/llms.txt

Create a ScrollTrigger instance without an associated tween, useful for triggering custom logic or callbacks based on scroll events. The `self` parameter provides access to the ScrollTrigger instance.

```javascript
// Standalone ScrollTrigger (no tween)
ScrollTrigger.create({
  trigger: "#section-2",
  start: "top center",
  onEnter: (self) => console.log("progress:", self.progress.toFixed(3))
});
```

### Key config options

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

The `pin` property allows an element to be fixed in place while the ScrollTrigger is active. Setting it to `true` pins the trigger element itself. It's recommended to animate child elements rather than the pinned element directly. `pinSpacing` defaults to `true`, adding a spacer to prevent layout collapse.

--------------------------------

### Key config options

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

The `start` property determines when the ScrollTrigger becomes active, with a default value of 'top bottom'. The `end` property defines when the ScrollTrigger becomes inactive, defaulting to 'bottom top'. If the end point is based on a different element, the `endTrigger` property can be used.

---

## GSAP SplitText — SplitText create types chars words lines autoSplit onSplit revert mask

*Context7 Library ID:* `/greensock/gsap-skills`

### SplitText.create()

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

Initializes SplitText to split the target element's text. The `vars` object configures the splitting behavior and options.

```APIDOC
## SplitText.create(target, vars)

### Description
Splits an element's text into characters, words, and/or lines for staggered or per-unit animation. Returns an instance with `chars`, `words`, `lines` properties.

### Parameters
#### target
- **target** (Selector | Element | Array) - The element(s) whose text content should be split.

#### vars
- **vars** (Object) - Configuration object for SplitText.
  - **type** (string) - Comma-separated: `"chars"`, `"words"`, `"lines"`. Default: `"chars,words,lines"`.
  - **charsClass** (string) - CSS class to apply to each character element.
  - **wordsClass** (string) - CSS class to apply to each word element.
  - **linesClass** (string) - CSS class to apply to each line element.
  - **aria** (string) - Accessibility setting: `"auto"` (default), `"hidden"`, or `"none"`.
  - **autoSplit** (boolean) - If `true`, reverts and re-splits when fonts load or element width changes. Animations must be created inside `onSplit()`.
  - **onSplit(self)** (function) - Callback when split completes or re-splits. Receives the SplitText instance. Returning a GSAP tween/timeline enables automatic revert/sync.
  - **mask** (string) - Wraps units in an element with `overflow: clip` for masking effects: `"lines"`, `"words"`, or `"chars"`.
  - **tag** (string) - Wrapper element tag; default: `"div"`.
  - **deepSlice** (boolean) - If `true` (default), subdivides nested elements spanning multiple lines.
  - **ignore** (Selector | Element | Array) - Selector or element(s) to leave unsplit.
  - **smartWrap** (boolean) - If splitting `chars` only, wraps words in a `white-space: nowrap` span to avoid mid-word line breaks. Default: `false`.
  - **wordDelimiter** (string | RegExp | Object) - Defines word boundaries. Default: `" "`.
  - **prepareText(text, parent)** (function) - Function to modify raw text before splitting.
  - **propIndex** (boolean) - If `true`, adds a CSS variable with index on each split element.
  - **reduceWhiteSpace** (boolean) - Collapses consecutive spaces; default: `true`.
  - **onRevert** (function) - Callback when the instance is reverted.

### Request Example
```javascript
gsap.registerPlugin(SplitText);

const split = SplitText.create(".heading", { type: "words, chars" });
gsap.from(split.chars, {
  opacity: 0,
  y: 20,
  stagger: 0.03,
  duration: 0.4
});
```

### Response
- **chars** (Array) - Array of character elements.
- **words** (Array) - Array of word elements.
- **lines** (Array) - Array of line elements.
- **masks** (Array) - Array of mask wrapper elements (if `mask` is set).

### Response Example
```json
{
  "chars": ["<span class=\"char\">H</span>", "<span class=\"char\">e</span>", ...],
  "words": ["<span class=\"word\">Hello</span>", ...],
  "lines": ["<span class=\"line\">Hello World</span>", ...]
}
```
```

--------------------------------

### SplitText: Basic Character Animation

Source: https://context7.com/greensock/gsap-skills/llms.txt

Split text into characters, words, or lines for individual animation. Use `SplitText.create()` and animate the resulting `chars`, `words`, or `lines` properties. Remember to call `split.revert()` for cleanup.

```javascript
import { gsap } from "gsap";
import { SplitText } from "gsap/SplitText";
gsap.registerPlugin(SplitText);

// Basic character animation
const split = SplitText.create(".heading", { type: "chars, words" });
gsap.from(split.chars, {
  y: 40,
  autoAlpha: 0,
  rotationX: -90,
  stagger: 0.02,
  duration: 0.5,
  ease: "back.out(1.7)",
  onComplete: () => split.revert()
});
```

--------------------------------

### SplitText: autoSplit for Responsive Text Animation

Source: https://context7.com/greensock/gsap-skills/llms.txt

Enable `autoSplit: true` for text that re-splits on resize, automatically calling `onSplit` each time. This is useful for responsive text animations where layout changes affect text segmentation.

```javascript
// autoSplit — re-splits on resize, calls onSplit each time; returned tween is killed on re-split
SplitText.create(".responsive-text", {
  type: "lines",
  autoSplit: true,
  mask: "lines",        // clips overflow during animation
  onSplit(self) {
    return gsap.from(self.lines, {
      y: "110%",        // slide from below the mask
      autoAlpha: 0,
      stagger: 0.07,
      duration: 0.6,
      ease: "power3.out"
    });
  }
});
```

--------------------------------

### SplitText with onSplit and autoSplit

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

Utilize the onSplit callback with autoSplit to re-split and animate text when fonts load or element width changes. Returning the animation from onSplit ensures proper cleanup and sync.

```javascript
SplitText.create(".split", {
  type: "lines",
  autoSplit: true,
  onSplit(self) {
    return gsap.from(self.lines, { y: 100, opacity: 0, stagger: 0.05, duration: 0.5 });
  }
});
```

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'mask' option allows for creating reveal effects by wrapping each text unit (lines, words, or chars) in an additional element with 'overflow: clip'. These mask elements can be accessed via the instance's 'masks' array.

---

## GSAP Flip — Flip getState from fit absolute layout transitions record state

*Context7 Library ID:* `/websites/gsap_v3`

### Capture element state with Flip.getState

Source: https://gsap.com/docs/v3/Plugins/Flip

Records the current position, size, and rotation of elements. Optionally include additional CSS properties using the props configuration.

```javascript
// returns a state object containing data about the elements' current position/size/rotation in the viewport
const state = Flip.getState(".targets");
```

```javascript
// record some extra properties (optional)
const state = Flip.getState(".targets", { props: "backgroundColor,color" });
```

--------------------------------

### Animate with Flip.from()

Source: https://gsap.com/docs/v3/Plugins/Flip/static.from%28%29

Animates elements from a previously captured state to their current state. Accepts standard tween properties like duration, ease, and onComplete. Returns a GSAP Timeline for further control. The 'absolute: true' option can be used for absolute positioning during the animation.

```javascript
// animate from the previous state to the current one:
Flip.from(state, {
  duration: 1,
  ease: "power1.inOut",
  absolute: true,
  onComplete: myFunc,
});
```

--------------------------------

### FLIP Animation Special Properties

Source: https://gsap.com/docs/v3/Plugins/Flip/static.from%28%29

Explains the 'absolute' and 'absoluteOnLeave' properties for the Flip.from() method in GSAP v3.

```APIDOC
## Special Properties for Flip.from()

The `Flip.from()` method in GSAP v3 accepts an optional properties object as its second parameter. In addition to standard tween properties (like `duration`, `ease`, `onComplete`), it can include the following special properties:

### `absolute`

*   **Description**: Specifies which of the animation targets should have `position: absolute` applied during the FLIP animation. This is useful for handling layout challenges, especially with flexbox and grid.
*   **Type**: `Boolean | String | Array | NodeList | Element`
*   **Details**: 
    *   If `true`, all targets are affected.
    *   A selector string (e.g., `".box"`), an array, NodeList, or a single Element can be used to specify a subset of targets.
    *   Setting `position: absolute` removes elements from the document flow, which might cause subsequent elements to collapse. Consider defining a subset that doesn't include the container to maintain layout.
*   **Added in**: GSAP 3.9.0

### `absoluteOnLeave`

*   **Description**: If `true`, any elements passed to the `onLeave()` callback will be set to `position: absolute` during the flip animation. This is helpful when hiding elements (e.g., with `display: none`) while still animating them out, ensuring they don't affect layout during the animation.
*   **Type**: `Boolean`
*   **Details**: Critical for animating elements that are hidden in the final state but need to be visible during the animation without altering the layout.
*   **Added in**: GSAP 3.9.0
```

--------------------------------

### Flip.from(state, vars)

Source: https://gsap.com/docs/v3/Plugins/Flip/static.from%28%29

Immediately moves or resizes targets to match a provided state object and animates them back to the current state.

```APIDOC
## Flip.from(state, vars)

### Description
Immediately moves/resizes the targets to match the provided `state` object, and then animates backwards to remove those offsets to end up at the current state. It returns a timeline animation.

### Parameters
- **state** (FlipState) - Required - A state object obtained from Flip.getState().
- **vars** (Object) - Required - The configuration object for the animation, supporting standard tween properties like `ease`, `duration`, and `onComplete`.

### Returns
- **Timeline** - A GSAP timeline animation instance.

### Request Example
```javascript
const state = Flip.getState(".targets");
// ... make DOM changes ...
Flip.from(state, {
  duration: 1,
  ease: "power1.inOut",
  absolute: true
});
```
```

--------------------------------

### Minimal Flip Animation Usage

Source: https://gsap.com/docs/v3/Plugins/Flip

Captures the initial state, performs DOM changes, and animates the transition to the final state.

```javascript
// grab state
const state = Flip.getState(squares);
  
// Make DOM or styling changes
switchItUp();
  
// Animate from the initial state to the end state
Flip.from(state, {duration: 2, ease: "power1.inOut"});
```

---

## GSAP Observer — Observer create target type onUp onDown onChange onMove debounce

*Context7 Library ID:* `/websites/gsap_v3`

### Observer.create(vars: Object)

Source: https://gsap.com/docs/v3/Plugins/Observer/static.create%28%29

Creates a new Observer instance based on the provided configuration object.

```APIDOC
## Observer.create(vars: Object)

### Description
Creates a new Observer instance according to the configuration details provided. This allows for tracking user interactions such as mouse wheel, touch, or pointer events.

### Parameters
- **vars** (Object) - Required - A configuration object containing settings and callbacks such as `target`, `type`, `onUp`, `onDown`, `debounce`, etc.

### Configuration Properties
- **axis** (string) - Optional - When `lockAxis: true` is set, the first drag movement sets the axis to "x" or "y".
- **capture** (Boolean) - Optional - If `true`, uses the capture phase for touch/pointer-related listeners.
- **debounce** (Boolean) - Optional - If `false`, disables event debouncing, checking immediately on every event.

### Usage Example
```javascript
Observer.create({
  target: window,
  type: "wheel,touch",
  onUp: () => previous(),
  onDown: () => next(),
});
```
```

--------------------------------

### Observer Callback Data Access

Source: https://gsap.com/docs/v3/Plugins/Observer/static.create%28%29

Describes how to access instance properties like velocity, delta, and target elements within an Observer callback function.

```APIDOC
## Observer Callback Data

### Description
Each callback in the Observer API receives the Observer instance as its only parameter. This allows direct access to instance properties including velocity, delta values, the target element, and the last event.

### Usage
```javascript
Observer.create({
  onChange: (self) => {
    console.log("velocity:", self.velocityX, self.velocityY, "delta:", self.deltaX, self.deltaY, "target element:", self.target, "last event:", self.event);
  }
});
```

### Available Properties
- **velocityX** (number) - The horizontal velocity.
- **velocityY** (number) - The vertical velocity.
- **deltaX** (number) - The horizontal change in position.
- **deltaY** (number) - The vertical change in position.
- **target** (Element) - The target element associated with the observer.
- **event** (Event) - The last event triggered.
```

--------------------------------

### Observer.create() Configuration

Source: https://gsap.com/docs/v3/Plugins/Observer

Configuration options for the Observer.create() method to customize event handling, axis locking, and callback functions.

```APIDOC
## Observer.create() Configuration

### Description
The configuration object passed to `Observer.create()` defines how the observer tracks user interactions, including mouse, touch, and pointer events.

### Parameters
#### Request Body
- **axis** (string) - Optional - When `lockAxis: true` is set, this property is set to "x" or "y" based on the initial drag direction.
- **capture** (boolean) - Optional - If `true`, uses the capture phase for event listeners.
- **debounce** (boolean) - Optional - If `true` (default), events are debounced for performance. If `false`, checks immediately on every event.
- **dragMinimum** (number) - Optional - Minimum distance in pixels to trigger a drag event.
- **id** (string) - Optional - An arbitrary string ID for retrieving the observer instance later.
- **ignore** (Element | String | Array) - Optional - Elements to ignore when triggering events.
- **lockAxis** (boolean) - Optional - If `true`, locks the observer to the first detected drag direction.
- **onChange** (function) - Optional - Callback for movement on either axis.
- **onChangeX** (function) - Optional - Callback for horizontal movement.
- **onChangeY** (function) - Optional - Callback for vertical movement.
- **onClick** (function) - Optional - Callback for click events.
- **onDown** (function) - Optional - Callback for downward motion.
- **onDragStart** (function) - Optional - Callback for start of drag.
- **onDrag** (function) - Optional - Callback during drag.
- **onDragEnd** (function) - Optional - Callback for end of drag.
- **onLeft** (function) - Optional - Callback for leftward motion.
- **onLockAxis** (function) - Optional - Callback when axis is locked.
- **onHover** (function) - Optional - Callback for hover events.
- **onHoverEnd** (function) - Optional - Callback for end of hover events.
```

### Plugins > Observer > Configuration Properties

Source: https://gsap.com/docs/v3/Plugins/Observer/static.create%28%29

The onMove callback triggers when the pointer moves over a target. Defining onMove causes the Observer to measure delta values while hovering, which triggers movement-related callbacks like onUp, onDown, and onChange during simple pointer movement. Without onMove, these movement callbacks typically only fire while the user is actively pressing and dragging.

--------------------------------

### Observer

Source: https://gsap.com/docs/v3/Plugins/Observer

Observer allows you to specify which event types to watch (wheel, touch, pointer, and/or scroll). It collects delta values on each requestAnimationFrame tick, debounced for performance, and automatically determines the biggest delta to trigger appropriate callbacks like onUp, onDown, or onDrag.

---

## Three.js Core — WebGLRenderer antialias alpha setPixelRatio setSize toneMapping ACESFilmic render

*Context7 Library ID:* `/mrdoob/three.js`

### Configure WebGL Renderer

Source: https://github.com/mrdoob/three.js/blob/dev/examples/misc_exporter_gltf.html

Initializes THREE.WebGLRenderer with antialiasing, sets pixel ratio and size, configures animation loop and tone mapping, then appends its DOM element.

```javascript
renderer = new THREE.WebGLRenderer( { antialias: true } );
renderer.setPixelRatio( window.devicePixelRatio );
renderer.setSize( window.innerWidth, window.innerHeight );
renderer.setAnimationLoop( animate );
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
container.appendChild( renderer.domElement );
```

--------------------------------

### Initialize Three.js WebGLRenderer with preserveDrawingBuffer

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/tips-preservedrawingbuffer.html

This snippet initializes a Three.js WebGLRenderer with `preserveDrawingBuffer: true` and `alpha: true`, allowing the buffer to be preserved after rendering. This is useful for operations like reading pixels or saving the canvas content.

```javascript
import * as THREE from 'three'; function main() { const canvas = document.querySelector( '#c' ); const renderer = new THREE.WebGLRenderer( { canvas, preserveDrawingBuffer: true, alpha: true, antialias: true } ); renderer.autoClearColor = false; const camera = new THREE.OrthographicCamera( - 2, 2, 1, - 1, - 1, 1 ); const scene = new THREE.Scene(); { const color = 0xFFFFFF; const intensity = 3; const light = new THREE.DirectionalLight( color, intensity ); light.position.set( - 1, 2, 4 ); scene.add( light ); } const boxWidth = 1; const boxHeight = 1; const boxDepth = 1; const geometry = new THREE.BoxGeometry( boxWidth, boxHeight, boxDepth ); const base = new THREE.Object3D(); scene.add( base ); base.scale.set( 0.1, 0.1, 0.1 ); function makeInstance( geometry, color, x, y, z ) { const material = new THREE.MeshPhongMaterial( { color } ); const cube = new THREE.Mesh( geometry, material ); base.add( cube ); cube.position.set( x, y, z ); return cube; } makeInstance( geometry, '#F00', - 2, 0, 0 ); makeInstance( geometry, '#FF0', 2, 0, 0 ); makeInstance( geometry, '#0F0', 0, - 2, 0 ); makeInstance( geometry, '#0FF', 0, 2, 0 ); makeInstance( geometry, '#00F', 0, 0, - 2 ); makeInstance( geometry, '#F0F', 0, 0, 2 ); function resizeRendererToDisplaySize( renderer ) { const canvas = renderer.domElement; const width = canvas.clientWidth; const height = canvas.clientHeight; const needResize = canvas.width !== width || canvas.height !== height; if ( needResize ) { renderer.setSize( width, height, false ); } return needResize; } const state = { x: 0, y: 0 }; function render( time ) { time *= 0.001; // convert to seconds if ( resizeRendererToDisplaySize( renderer ) ) { const canvas = renderer.domElement; camera.right = canvas.clientWidth / canvas.clientHeight; camera.left = - camera.right; camera.updateProjectionMatrix(); } base.position.set( state.x, state.y, 0 ); base.rotation.x = time; base.rotation.y = time * 1.11; renderer.render( scene, camera ); requestAnimationFrame( render ); } requestAnimationFrame( render ); function getCanvasRelativePosition( event ) { const rect = canvas.getBoundingClientRect(); return { x: ( event.clientX - rect.left ) * canvas.width / rect.width, y: ( event.clientY - rect.top ) * canvas.height / rect.height, }; } const temp = new THREE.Vector3(); function setPosition( e ) { const pos = getCanvasRelativePosition( e ); const x = pos.x / canvas.width * 2 - 1; const y = pos.y / canvas.height * - 2 + 1; temp.set( x, y, 0 ).unproject( camera ); state.x = temp.x; state.y = temp.y; } canvas.addEventListener( 'mousemove', setPosition ); canvas.addEventListener( 'touchmove', ( e ) => { e.preventDefault(); setPosition( e.touches[ 0 ] ); }, { passive: false } ); } main();
```

--------------------------------

### WebGLRenderer.setPixelRatio and setSize with updateStyle false

Source: https://github.com/mrdoob/three.js/blob/dev/src/renderers/WebGLRenderer.js

setPixelRatio stores the value and calls setSize with updateStyle=false, meaning only the drawing buffer dimensions change without touching the canvas CSS style.

```javascript
	this.setPixelRatio = function ( value ) {

		if ( value === undefined ) return;

		_pixelRatio = value;

		this.setSize( _width, _height, false );

	};

	this.setSize = function ( width, height, updateStyle = true ) {

		if ( xr.isPresenting ) {

			warn( 'WebGLRenderer: Can\'t change size while VR device is presenting.' );
			return;

		}

		_width = width;
		_height = height;

		canvas.width = Math.floor( width * _pixelRatio );
		canvas.height = Math.floor( height * _pixelRatio );

		if ( updateStyle === true ) {

			canvas.style.width = width + 'px';
			canvas.style.height = height + 'px';

		}

		if ( output !== null ) {

			output.setSize( canvas.width, canvas.height );

		}

		this.setViewport( 0, 0, width, height );

	};
```

--------------------------------

### WebGLRenderer with ACES tone mapping and EffectComposer/RenderPass/UnrealBloomPass

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_postprocessing_unreal_bloom.html

Configures WebGLRenderer with ACESFilmicToneMapping (sRGB output by default), then sets up EffectComposer with RenderPass, UnrealBloomPass, and OutputPass for correct color space handling.

```javascript
renderer = new THREE.WebGLRenderer( { antialias: true } );
renderer.setPixelRatio( window.devicePixelRatio );
renderer.setSize( window.innerWidth, window.innerHeight );
renderer.setAnimationLoop( animate );
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const renderScene = new RenderPass( scene, camera );

const bloomPass = new UnrealBloomPass( new THREE.Vector2( window.innerWidth, window.innerHeight ), 1.5, 0.4, 0.85 );
bloomPass.threshold = params.threshold;
bloomPass.strength = params.strength;
bloomPass.radius = params.radius;

const outputPass = new OutputPass();

composer = new EffectComposer( renderer );
composer.addPass( renderScene );
composer.addPass( bloomPass );
composer.addPass( outputPass );
```

### WebGLRenderer > toneMapping

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html

The `toneMapping` property defines the tone mapping technique used by the renderer, with options such as `NoToneMapping`, `LinearToneMapping`, `ReinhardToneMapping`, `CineonToneMapping`, `ACESFilmicToneMapping`, `CustomToneMapping`, `AgXToneMapping`, and `NeutralToneMapping`. The default tone mapping technique is `NoToneMapping`.

---

## Three.js Geometries — TorusGeometry CircleGeometry BoxGeometry parameters radius tube arc

*Context7 Library ID:* `/mrdoob/three.js`

### new TorusGeometry( radius : number, tube : number, radialSegments : number, tubularSegments : number, arc : number, thetaStart : number, thetaLength : number )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/TorusGeometry.html.md

Constructs a new torus geometry with specified dimensions and segmentation.

```APIDOC
## new TorusGeometry( radius : number, tube : number, radialSegments : number, tubularSegments : number, arc : number, thetaStart : number, thetaLength : number )

### Description
Constructs a new torus geometry.

### Parameters
- **radius** (number) - Optional - Radius of the torus, from the center of the torus to the center of the tube. Default is `1`.
- **tube** (number) - Optional - Radius of the tube. Must be smaller than `radius`. Default is `0.4`.
- **radialSegments** (number) - Optional - The number of radial segments. Default is `12`.
- **tubularSegments** (number) - Optional - The number of tubular segments. Default is `48`.
- **arc** (number) - Optional - Central angle in radians. Default is `Math.PI*2`.
- **thetaStart** (number) - Optional - Start of the tubular sweep in radians. Default is `0`.
- **thetaLength** (number) - Optional - Length of the tubular sweep in radians. Default is `Math.PI*2`.
```

--------------------------------

### Create and Control THREE.TorusGeometry with GUI

Source: https://github.com/mrdoob/three.js/blob/dev/docs/scenes/geometry-browser.html

Defines a TorusGeometry and sets up dat.GUI controls for its radius, tube, radialSegments, tubularSegments, and arc parameters. The geometry updates dynamically on parameter changes.

```javascript
TorusGeometry: function ( mesh ) { const data = { radius: 10, tube: 3, radialSegments: 16, tubularSegments: 100, arc: twoPi }; function generateGeometry() { updateGroupGeometry( mesh, new TorusGeometry( data.radius, data.tube, data.radialSegments, data.tubularSegments, data.arc ) ); } const folder = gui.addFolder( 'THREE.TorusGeometry' ); folder.add( data, 'radius', 1, 20 ).onChange( generateGeometry ); folder.add( data, 'tube', 0.1, 10 ).onChange( generateGeometry ); folder.add( data, 'radialSegments', 2, 30 ).step( 1 ).onChange( generateGeometry ); folder.add( data, 'tubularSegments', 3, 200 ).step( 1 ).onChange( generateGeometry ); folder.add( data, 'arc', 0.1, twoPi ).onChange( generateGeometry ); generateGeometry(); },
```

--------------------------------

### Create a TorusGeometry (JavaScript)

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/primitives.html

Creates a THREE.TorusGeometry to form a donut-like shape. Parameters control the overall radius, tube radius, and segment counts.

```javascript
{ const radius = 5; const tubeRadius = 2; const radialSegments = 8; const tubularSegments = 24; addSolidGeometry( 0, - 1, new THREE.TorusGeometry( radius, tubeRadius, radialSegments, tubularSegments ) ); }
```

--------------------------------

### new CircleGeometry(radius, segments, thetaStart, thetaLength)

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/CircleGeometry.html

Constructs a new circle geometry with specified dimensions and angular range. This allows for creating full circles, partial arcs, or regular polygons by adjusting the number of segments.

```APIDOC
## Constructor CircleGeometry

### Description
Constructs a new circle geometry.

### Signature
new CircleGeometry( radius : number, segments : number, thetaStart : number, thetaLength : number )

### Parameters
- **radius** (number) - Optional - Radius of the circle. Default is `1`.
- **segments** (number) - Optional - Number of segments (triangles), minimum = `3`. Default is `32`.
- **thetaStart** (number) - Optional - Start angle for first segment in radians. Default is `0`.
- **thetaLength** (number) - Optional - The central angle, often called theta, of the circular sector in radians. The default value results in a complete circle. Default is `Math.PI*2`.

### Example
```javascript
const geometry = new THREE.CircleGeometry( 5, 32 );
const material = new THREE.MeshBasicMaterial( { color: 0xffff00 } );
const circle = new THREE.Mesh( geometry, material );
scene.add( circle )
```
```

### RingGeometry > Constructor

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/RingGeometry.html.md

RingGeometry constructs a two-dimensional ring geometry, defined by its inner and outer radii, and the number of segments for its circumference and thickness. Key parameters include `innerRadius` (default 0.5), `outerRadius` (default 1), `thetaSegments` (default 32, minimum 3 for roundness), and `phiSegments` (default 1, minimum 1). The ring's arc can be controlled with `thetaStart` (default 0) and `thetaLength` (default Math.PI*2).

---

## Three.js Materials & Lights — MeshStandardMaterial color metalness roughness emissive DirectionalLight PointLight AmbientLight

*Context7 Library ID:* `/mrdoob/three.js`

### Create THREE.MeshStandardMaterial from URL hash

Source: https://github.com/mrdoob/three.js/blob/dev/utils/docs/template/static/scenes/material-browser.html

Instantiates a THREE.MeshStandardMaterial with a default color and configures its GUI controls. It disables all scene lights, relying solely on the scene environment for lighting.

```javascript
case 'MeshStandardMaterial' : material = new THREE.MeshStandardMaterial( { color: 0x049EF4 } ); guiMaterial( gui, mesh, material, geometry ); guiMeshStandardMaterial( gui, mesh, material, geometry ); // only use scene environment light1.visible = false; light2.visible = false; light3.visible = false; return material; break;
```

--------------------------------

### emissive

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/MeshLambertMaterial.html

Configures the emissive (light) color of the material, which is a solid color unaffected by other lighting.

```APIDOC
## Property: emissive

### Type
Color

### Description
Emissive (light) color of the material, essentially a solid color unaffected by other lighting.

### Default Value
(0,0,0)
```

--------------------------------

### MeshStandardMaterial Properties

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/MeshStandardMaterial.html.md

Configurable properties of the MeshStandardMaterial, affecting its visual appearance and behavior, including various texture maps, colors, and shading options.

```APIDOC
## MeshStandardMaterial Properties

### .alphaMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: The alpha map is a grayscale texture that controls the opacity across the surface (black: fully transparent; white: fully opaque). Only the color of the texture is used, ignoring the alpha channel if one exists. For RGB and RGBA textures, the renderer will use the green channel when sampling this texture due to the extra bit of precision provided for green in DXT-compressed and uncompressed RGB 565 formats. Luminance-only and luminance/alpha textures will also still work as expected. `alphaMap` represents non-color data. Any texture assigned must have `texture.colorSpace = NoColorSpace` (default).

### .aoMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: The red channel of this texture is used as the ambient occlusion map. Requires a second set of UVs. `aoMap` represents non-color data. Any texture assigned must have `texture.colorSpace = NoColorSpace` (default).

### .aoMapIntensity : number
- **Type**: number
- **Default**: `1`
- **Description**: Intensity of the ambient occlusion effect. Range is `[0,1]`, where `0` disables ambient occlusion. Where intensity is `1` and the AO map's red channel is also `1`, ambient light is fully occluded on a surface.

### .bumpMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: The texture to create a bump map. The black and white values map to the perceived depth in relation to the lights. Bump doesn't actually affect the geometry of the object, only the lighting. If a normal map is defined this will be ignored. `bumpMap` represents non-color data. Any texture assigned must have `texture.colorSpace = NoColorSpace` (default).

### .bumpScale : number
- **Type**: number
- **Default**: `1`
- **Description**: How much the bump map affects the material. Typical range is `[0,1]`.

### .color : Color
- **Type**: Color
- **Default**: `(1,1,1)`
- **Description**: Color of the material.

### .displacementBias : number
- **Type**: number
- **Default**: `0`
- **Description**: The offset of the displacement map's values on the mesh's vertices. The bias is added to the scaled sample of the displacement map. Without a displacement map set, this value is not applied.

### .displacementMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: The displacement map affects the position of the mesh's vertices. Unlike other maps which only affect the light and shade of the material the displaced vertices can cast shadows, block other objects, and otherwise act as real geometry. The displacement texture is an image where the value of each pixel (white being the highest) is mapped against, and repositions, the vertices of the mesh. For best results, pair a displacement map with a matching normal map, since the renderer can not recompute surface normals from the displaced vertices. `displacementMap` represents non-color data. Any texture assigned must have `texture.colorSpace = NoColorSpace` (default).

### .displacementScale : number
- **Type**: number
- **Default**: `0`
- **Description**: How much the displacement map affects the mesh (where black is no displacement, and white is maximum displacement). Without a displacement map set, this value is not applied.

### .emissive : Color
- **Type**: Color
- **Default**: `(0,0,0)`
- **Description**: Emissive (light) color of the material, essentially a solid color unaffected by other lighting.

### .emissiveIntensity : number
- **Type**: number
- **Default**: `1`
- **Description**: Intensity of the emissive light. Modulates the emissive color.

### .emissiveMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: Set emissive (glow) map. The emissive map color is modulated by the emissive color and the emissive intensity. If you have an emissive map, be sure to set the emissive color to something other than black. `emissiveMap` represents color data, and the texture must be assigned a [Texture#colorSpace](Texture.html#colorSpace). Most `emissiveMap` textures set `texture.colorSpace = SRGBColorSpace`.

### .envMap : Texture
- **Type**: Texture
- **Default**: `null`
- **Description**: The environment map. To ensure a physically correct rendering, environment maps are internally pre-processed with [PMREMGenerator](PMREMGenerator.html). `envMap` represents luminance data, and the texture must be assigned a [Texture#colorSpace](Texture.html#colorSpace). Most `envMap` textures set `texture.colorSpace = LinearSRGBColorSpace` and use float-type formats such as `.exr` or `.hdr`.

### .envMapIntensity : number
- **Type**: number
- **Default**: `1`
- **Description**: Scales the effect of the environment map by multiplying its color.

### .envMapRotation : Euler
- **Type**: Euler
- **Default**: `(0,0,0)`
- **Description**: The rotation of the environment map in radians.

### .flatShading : boolean
- **Type**: boolean
- **Default**: `false`
- **Description**: Whether the material is rendered with flat shading or not.

### .fog : boolean
- **Type**: boolean
- **Default**: `true`
- **Description**: Whether the material is affected by fog or not.
```

### Materials > MeshStandardMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/materials.html

MeshStandardMaterial uses roughness and metalness settings rather than shininess. Roughness (0 to 1) is the opposite of shininess, where high roughness results in soft reflections like a baseball. Metalness (0 to 1) determines how metallic the material behaves, as metals reflect light differently than non-metals.

--------------------------------

### MeshPhysicalMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/MeshPhysicalMaterial.html

MeshPhysicalMaterial extends MeshStandardMaterial, offering advanced physically-based rendering properties. These include Anisotropy for brushed metals, Clearcoat for layered surfaces like car paints, Iridescence for effects seen on soap bubbles, and physically-based transparency for realistic glass. It also provides advanced reflectivity and Sheen for fabric materials.

---

## Three.js Memory Management — dispose geometry material texture renderer traverse clean GPU memory leak

*Context7 Library ID:* `/mrdoob/three.js`

### Dispose Three.js Scene Resources

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_loader_svg.html

Traverses a Three.js scene to dispose of geometries, materials, and textures for meshes and lines, releasing GPU memory.

```javascript
function disposeScene( scene ) { scene.traverse( function ( object ) { if ( object.isMesh || object.isLine ) { object.geometry.dispose(); if ( object.material.map ) object.material.map.dispose(); object.material.dispose(); } } ); }
```

--------------------------------

### Clean Scene Meshes and Dispose Resources

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_instancing_performance.html

Removes all meshes from the scene and disposes of their materials and geometries to prevent memory leaks before rebuilding the scene.

```javascript
function clean() {

	const meshes = [];

	scene.traverse( function ( object ) {

		if ( object.isMesh ) meshes.push( object );

	} );

	for ( let i = 0; i < meshes.length; i ++ ) {

		const mesh = meshes[ i ];
		mesh.material.dispose();
		mesh.geometry.dispose();
		scene.remove( mesh );

	}

}
```

--------------------------------

### Three.js WebGL Memory Test Initialization and Animation

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_test_memory.html

Initializes a Three.js scene with a camera and renderer, then continuously creates and disposes of meshes, geometries, textures, and materials to test WebGL memory management.

```javascript
import * as THREE from 'three';
let camera, scene, renderer;
init();
function init() {
  const container = document.createElement( 'div' );
  document.body.appendChild( container );
  camera = new THREE.PerspectiveCamera( 60, window.innerWidth / window.innerHeight, 1, 10000 );
  camera.position.z = 200;
  scene = new THREE.Scene();
  scene.background = new THREE.Color( 0xffffff );
  renderer = new THREE.WebGLRenderer();
  renderer.setPixelRatio( window.devicePixelRatio );
  renderer.setSize( window.innerWidth, window.innerHeight );
  renderer.setAnimationLoop( animate );
  container.appendChild( renderer.domElement );
}
function createImage() {
  const canvas = document.createElement( 'canvas' );
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext( '2d' );
  context.fillStyle = 'rgb(' + Math.floor( Math.random() * 256 ) + ',' + Math.floor( Math.random() * 256 ) + ',' + Math.floor( Math.random() * 256 ) + ')';
  context.fillRect( 0, 0, 256, 256 );
  return canvas;
}
// function animate() {
  const geometry = new THREE.SphereGeometry( 50, Math.random() * 64, Math.random() * 32 );
  const texture = new THREE.CanvasTexture( createImage() );
  const material = new THREE.MeshBasicMaterial( { map: texture, wireframe: true } );
  const mesh = new THREE.Mesh( geometry, material );
  scene.add( mesh );
  renderer.render( scene, camera );
  scene.remove( mesh );
  // clean up
  geometry.dispose();
  material.dispose();
  texture.dispose();
}
```

--------------------------------

### JavaScript ResourceTracker Class for Three.js Cleanup

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/cleanup-loaded-files.html

A utility class designed to track and manage Three.js resources (geometries, materials, textures, objects) to ensure proper disposal and prevent memory leaks. Resources are added with track() and released with dispose().

```javascript
class ResourceTracker {
  constructor() {
    this.resources = new Set();
  }
  track( resource ) {
    if ( ! resource ) {
      return resource;
    }
    // handle children and when material is an array of materials or
    // uniform is array of textures
    if ( Array.isArray( resource ) ) {
      resource.forEach( resource => this.track( resource ) );
      return resource;
    }
    if ( resource.dispose || resource instanceof THREE.Object3D ) {
      this.resources.add( resource );
    }
    if ( resource instanceof THREE.Object3D ) {
      this.track( resource.geometry );
      this.track( resource.material );
      this.track( resource.children );
    } else if ( resource instanceof THREE.Material ) {
      // We have to check if there are any textures on the material
      for ( const value of Object.values( resource ) ) {
        if ( value instanceof THREE.Texture ) {
          this.track( value );
        }
      }
      // We also have to check if any uniforms reference textures or arrays of textures
      if ( resource.uniforms ) {
        for ( const value of Object.values( resource.uniforms ) ) {
          if ( value ) {
            const uniformValue = value.value;
            if ( uniformValue instanceof THREE.Texture || Array.isArray( uniformValue ) ) {
              this.track( uniformValue );
            }
          }
        }
      }
    }
    return resource;
  }
  untrack( resource ) {
    this.resources.delete( resource );
  }
  dispose() {
    for ( const resource of this.resources ) {
      if ( resource instanceof THREE.Object3D ) {
        if ( resource.parent ) {
          resource.parent.remove( resource );
        }
      }
      if ( resource.dispose ) {
        resource.dispose();
      }
    }
    this.resources.clear();
  }
}
```

### Cleanup > Handling Materials and Textures

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/cleanup.html

Effective resource management requires inspecting materials for textures, as materials may be organized in arrays or contain uniforms that reference textures. A robust tracking system should iterate through material properties and uniforms to identify all texture resources for eventual disposal. This prevents memory leaks when objects are removed from a scene and are no longer needed.

---

