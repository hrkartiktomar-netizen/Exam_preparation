# Ultra-Deep Technical Architecture Manual (Lenis, GSAP, Three.js)

> **Authoritative Source:** Context7 MCP (`https://mcp.context7.com/mcp`)
> **Generated On:** 2026-08-31T20:33:39.204Z
> **Scope:** Low-level engine internals, linked list data structures, delta normalization, WebGL state caching, GPU pipeline matrices, and mathematical algorithms.

---

## Lenis Delta Normalization & Wheel Math

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `normalizeWheel deltaMode wheel touch velocity clamp damp math`

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

### Listening to the scroll event and reading scroll position

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

The `on` method accepts a `'scroll'` event and passes the Lenis instance to the callback. The Lenis instance exposes getters like `scroll`, `animatedScroll`, `velocity`, `progress`, `direction`, and `isScrolling` that can be read at every scroll frame.

```typescript
on(event: 'scroll', callback: ScrollCallback): () => void
on(event: 'virtual-scroll', callback: VirtualScrollCallback): () => void
on(event: LenisEvent, callback: ScrollCallback | VirtualScrollCallback) {
  return this.emitter.on(event, callback as (...args: unknown[]) => void)
}

// The scroll event emits the entire Lenis instance:
private emit() {
  this.emitter.emit('scroll', this)
}

// ScrollCallback receives the Lenis instance:
export type ScrollCallback = (lenis: Lenis) => void

// Getters you can read in the callback:
get scroll() { /* returns animatedScroll (modulo'd if infinite) */ }
get animatedScroll() { /* the animated scroll value */ }
get progress() { /* scroll / limit */ }
get velocity() { /* current velocity */ }
get direction() { /* 1, -1, or 0 */ }
get isScrolling() { /* false, 'native', or 'smooth' */ }
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

### Settings

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis provides several settings to control scroll behavior, including touchInertiaExponent for syncTouch strength and multipliers for touch and wheel events. The virtualScroll function allows for manual modification of events, enabling developers to slow down scrolling or conditionally disable smoothing based on specific keys. The wrapper setting defines the scroll container, which defaults to the window object.

--------------------------------

### Settings

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis provides various settings to control scrolling behavior, including orientation, interpolation intensity, and touch synchronization. Key features include the ability to enable infinite scrolling, honor user reduced motion preferences, and manage overscroll behavior similar to CSS standards. Users can also implement custom logic to prevent smooth scrolling on specific elements or stop inertia during navigation.

---

## Lenis Dimension & Limit Calculation

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `dimensions scrollHeight clientHeight limit clamp subpixel zoom ResizeObserver`

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

--------------------------------

### Scroll getter with modulo wrapping — core infinite mechanism

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

The public `scroll` getter always returns `modulo(animatedScroll, limit)` when infinite is enabled, keeping the reported scroll value in `[0, limit)` even as the internal animatedScroll grows unboundedly. Combined with duplicated DOM content, this creates the seamless infinite scroll illusion.

```typescript
get scroll() {
  return this.options.infinite
    ? modulo(this.animatedScroll, this.limit)
    : this.animatedScroll
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

### Known causes of performance problems / janky scroll

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

The README documents two specific options that cause performance issues: `allowNestedScroll` (DOM tree checked on every scroll event — use `data-lenis-prevent` instead) and `naiveDimensions` (naive dimension calculation has a performance impact). These are the primary built-in sources of stuttering.

```markdown
| `allowNestedScroll`     | `boolean`                  | `false`                                            | Automatically allow nested scrollable elements to scroll natively. This is the simplest way to handle nested scroll. ⚠️ Can create performance issues since it checks the DOM tree on every scroll event. If that's a concern, use `prevent` option instead.          |
| `naiveDimensions`       | `boolean`                  | `false`                                            | If `true`, Lenis will use naive dimensions calculation. ⚠️ Be careful, this has a performance impact.
```

### Settings > autoResize

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

The autoResize option defaults to true, allowing the instance to resize automatically using ResizeObserver. If set to false, developers must manually trigger the resize method to update the instance.

---

## Lenis Touch & Overscroll iOS

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `touchInertiaExponent syncTouch overscroll-behavior rubber band iOS touchmove`

### Disable Reduced Motion Respect

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Override the default behavior of honoring the prefers-reduced-motion media query by setting respectReducedMotion to false.

```js
const lenis = new Lenis({
  respectReducedMotion: false,
})
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

### Settings

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis provides several settings to control scroll behavior, including touchInertiaExponent for syncTouch strength and multipliers for touch and wheel events. The virtualScroll function allows for manual modification of events, enabling developers to slow down scrolling or conditionally disable smoothing based on specific keys. The wrapper setting defines the scroll container, which defaults to the window object.

--------------------------------

### Settings

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis provides various settings to control scrolling behavior, including orientation, interpolation intensity, and touch synchronization. Key features include the ability to enable infinite scrolling, honor user reduced motion preferences, and manage overscroll behavior similar to CSS standards. Users can also implement custom logic to prevent smooth scrolling on specific elements or stop inertia during navigation.

--------------------------------

### Considerations > Reduced motion

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis automatically respects the user's prefers-reduced-motion system setting. When reduced motion is enabled, smoothing is disabled and programmatic scrolls jump instantly to their target, though the library continues to run to maintain synchronization. Developers can opt out of this behavior by setting respectReducedMotion to false, or check the lenis.prefersReducedMotion property to adjust their own animations accordingly.

---

## Lenis Architecture & Event Loop

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `Animate class advance damp deltaTime emit isScrolling setScroll`

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

--------------------------------

### onNativeScroll — silent during smooth, catches native-only scrolls

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

The native scroll event listener. During smooth scrolling, isScrolling is 'smooth', so the guard at line 625 prevents any action. It only syncs animatedScroll/targetScroll to actualScroll when scrolling is idle or already native. This confirms that during the per-frame onUpdate cycle, the native scroll event triggered by setScroll is intentionally a no-op — not delayed, but silently dropped. The _preventNextNativeScrollEvent flag only guards against the completion-frame native scroll to avoid a double-emit.

```typescript
  private onNativeScroll = () => {
    if (this._resetVelocityTimeout !== null) {
      clearTimeout(this._resetVelocityTimeout)
      this._resetVelocityTimeout = null
    }

    if (this._preventNextNativeScrollEvent) {
      this._preventNextNativeScrollEvent = false
      return
    }

    if (this.isScrolling === false || this.isScrolling === 'native') {
      const lastScroll = this.animatedScroll
      this.animatedScroll = this.targetScroll = this.actualScroll
      this.lastVelocity = this.velocity
      this.velocity = this.animatedScroll - lastScroll
      this.direction = Math.sign(
        this.animatedScroll - lastScroll
      ) as Lenis['direction']

      if (!this.isStopped) {
        this.isScrolling = 'native'
      }

      this.emit()

      if (this.velocity !== 0) {
        this._resetVelocityTimeout = setTimeout(() => {
          this.lastVelocity = this.velocity
          this.velocity = 0
          this.isScrolling = false
          this.emit()
        }, 400)
      }
    }
  }
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

### Listening to the scroll event and reading scroll position

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

The `on` method accepts a `'scroll'` event and passes the Lenis instance to the callback. The Lenis instance exposes getters like `scroll`, `animatedScroll`, `velocity`, `progress`, `direction`, and `isScrolling` that can be read at every scroll frame.

```typescript
on(event: 'scroll', callback: ScrollCallback): () => void
on(event: 'virtual-scroll', callback: VirtualScrollCallback): () => void
on(event: LenisEvent, callback: ScrollCallback | VirtualScrollCallback) {
  return this.emitter.on(event, callback as (...args: unknown[]) => void)
}

// The scroll event emits the entire Lenis instance:
private emit() {
  this.emitter.emit('scroll', this)
}

// ScrollCallback receives the Lenis instance:
export type ScrollCallback = (lenis: Lenis) => void

// Getters you can read in the callback:
get scroll() { /* returns animatedScroll (modulo'd if infinite) */ }
get animatedScroll() { /* the animated scroll value */ }
get progress() { /* scroll / limit */ }
get velocity() { /* current velocity */ }
get direction() { /* 1, -1, or 0 */ }
get isScrolling() { /* false, 'native', or 'smooth' */ }
```

---

## GSAP Linked List & Tick Architecture

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `gsap linked list timeline _first _last _next ticker delta time`

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

### Add and Use Labels in GSAP Timeline

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

Labels provide readable markers within a timeline, improving maintainability. They can be used for precise positioning and for controlling playback.

```javascript
tl.addLabel("intro", 0);
tl.to(".a", { x: 100 }, "intro");
tl.addLabel("outro", "+=0.5");
tl.to(".b", { opacity: 0 }, "outro");
tl.play("outro");  // start from "outro"
tl.tweenFromTo("intro", "outro"); // pauses the timeline and returns a new Tween that animates the timeline's playhead from intro to outro with no ease.
```

--------------------------------

### Position Parameter Examples in GSAP Timeline

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

The position parameter (third argument) controls where a tween is placed within the timeline. It supports absolute times, relative offsets, labels, and relative placement to other tweens.

```javascript
tl.to(".a", { x: 100 }, 0);           // at 0
tl.to(".b", { y: 50 }, "+=0.5");      // 0.5s after last end
tl.to(".c", { opacity: 0 }, "<");     // same start as previous
tl.to(".d", { scale: 2 }, "<0.2");    // 0.2s after previous start
```

### GSAP Timeline > Controlling Playback

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-timeline/SKILL.md

Timelines offer various methods for controlling playback, including `play()`, `pause()`, `reverse()`, `restart()`, seeking to a specific time with `time()`, or a percentage with `progress()`, and stopping all animations with `kill()`.

--------------------------------

### Skills > gsap-timeline

Source: https://github.com/greensock/gsap-skills/blob/main/skills/llms.txt

GSAP Timelines (`gsap.timeline()`) allow for sequencing animations using position parameters and labels. They support nesting timelines and controlling playback, making them ideal for choreographing multi-step animations and defining animation order.

---

## GSAP Transform Matrix & GPU Compositing

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `Matrix2D force3D will-change transform matrix layout thrashing GPU`

### Animate Compositor-Only Properties with GSAP

Source: https://context7.com/greensock/gsap-skills/llms.txt

Animate `transform` properties (x, y, scale, rotation) and `opacity` to ensure animations run on the compositor layer for smooth 60fps performance. Avoid animating layout-triggering properties like width or top.

```javascript
import { gsap } from "gsap";

// ✅ Compositor-only properties — smooth 60fps
gsap.to(".box", { x: 200, y: 100, scale: 1.2, rotation: 45, autoAlpha: 0.5, duration: 0.6 });

// ❌ Avoid — triggers layout recalculation
// gsap.to(".box", { width: 200, top: 100, marginLeft: 20 });

// will-change: hint browser to promote to own layer (use sparingly)
// Applied via CSS on elements you know will animate: will-change: transform;
```

--------------------------------

### CSS will-change for Animation Hinting

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-performance/SKILL.md

Use the CSS will-change property on elements that will be animated to hint the browser to promote the layer, potentially improving rendering performance. Apply this only to elements that are actively animating.

```css
will-change: transform;
```

### GSAP Performance > Do Not

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-performance/SKILL.md

Avoid animating layout-altering properties like width, height, top, or left when transforms can achieve the same visual result. Do not apply `will-change` or `force3D` unnecessarily. Refrain from creating excessive overlapping tweens or ScrollTriggers without testing on lower-end devices, and always manage cleanup to prevent performance degradation.

--------------------------------

### GSAP Performance > Batch Reads and Writes

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-performance/SKILL.md

When mixing GSAP animations with direct DOM reads and writes, avoid interleaving them in a way that causes repeated layout recalculations (layout thrashing). It's more efficient to perform all DOM reads first, followed by all DOM writes, or to let GSAP manage the writes in a single batch.

--------------------------------

### GSAP Performance > Prefer Transform and Opacity

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-performance/SKILL.md

Prefer animating CSS transform properties (like x, y, scale, rotation) and opacity. These properties are handled by the compositor, minimizing layout and paint operations. Avoid animating layout-heavy properties such as width, height, or margins when a transform can achieve a similar visual effect.

---

## GSAP ScrollTrigger Pin Spacer & Repositioning

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `ScrollTrigger pin spacer pinType transform fixed anticipatePin refreshPriority`

### Pinning Element with ScrollTrigger

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Pins the trigger element in place for the duration of the scroll range. `pinSpacing: true` (default) adds a spacer to prevent layout collapse; set to `false` if layout is handled separately.

```javascript
scrollTrigger: {
  trigger: ".section",
  start: "top top",
  end: "+=1000",   // pin for 1000px scroll
  pin: true,
  scrub: 1
}
```

### Key config options

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

The `pin` property allows an element to be fixed in place while the ScrollTrigger is active. Setting it to `true` pins the trigger element itself. It's recommended to animate child elements rather than the pinned element directly. `pinSpacing` defaults to `true`, adding a spacer to prevent layout collapse.

--------------------------------

### Pinning

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Pinning keeps a trigger element fixed in place for the duration of its active scroll range. The `pinSpacing` option, which defaults to `true`, automatically adds a spacer element to prevent layout collapse when the pinned element is set to `position: fixed`. Set `pinSpacing: false` only if you are managing the layout separately.

--------------------------------

### ScrollTrigger.scrollerProxy() > vars

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

When configuring ScrollTrigger.scrollerProxy(), you provide 'scrollTop' and/or 'scrollLeft' functions that act as both getters and setters. Additionally, optional vars include 'getBoundingClientRect' for the scroller's dimensions, 'scrollWidth'/'scrollHeight' getters/setters if the library exposes different dimensions, 'fixedMarkers' to handle fixed positioning of markers, and 'pinType' ('fixed' or 'transform') to control how pinning is applied.

--------------------------------

### GSAP Performance > ScrollTrigger and Performance

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-performance/SKILL.md

When using ScrollTrigger, `pin: true` promotes the pinned element, so only pin essential elements. Using `scrub` with a small value can reduce work during scrolling. Call `ScrollTrigger.refresh()` only when the layout has actually changed, and consider debouncing it for resize events.

---

## GSAP ScrollTrigger FastScroll & Invalidation

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `ScrollTrigger fastScrollEnd preventOverlaps invalidateOnRefresh autoRefresh`

No documentation in "/greensock/gsap-skills" matched this query. Try a more specific query with different terms, or search for another library that covers this topic.

---

## GSAP SplitText DeepSlice & Graphemes

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `SplitText deepSlice smartWrap wordDelimiter mask lines words chars`

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

### SplitText with onSplit() Callback

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

Demonstrates using the `onSplit()` callback to create animations that are automatically managed during re-splitting when `autoSplit` is enabled.

```APIDOC
## SplitText with autoSplit and onSplit()

### Description
When `autoSplit` is `true`, the `onSplit()` callback is invoked on re-splits. Returning a GSAP tween or timeline from `onSplit()` allows SplitText to automatically handle the cleanup and progress synchronization of that animation.

### Method
`SplitText.create(target, vars)`

### Parameters
- **vars.autoSplit** (boolean): When `true`, reverts and re-splits when fonts finish loading or element width changes (for lines). Animations must be created inside `onSplit()`.
- **vars.onSplit(self)** (function): Callback when split completes (and on each re-split if `autoSplit` is `true`). Receives the SplitText instance (`self`). Returning a GSAP tween or timeline enables automatic revert/sync of that animation when re-splitting.

### Request Example
```javascript
SplitText.create(".split", {
  type: "lines",
  autoSplit: true,
  onSplit(self) {
    // Return the animation to be managed by SplitText
    return gsap.from(self.lines, {
      y: 100,
      opacity: 0,
      stagger: 0.05,
      duration: 0.5
    });
  }
});
```
```

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'type' configuration option for SplitText determines what units to split the text into, with options including 'chars', 'words', and 'lines'. The default is 'chars,words,lines'. For performance, it's recommended to only split the units that are actually needed for animation. If splitting only characters, 'smartWrap: true' can prevent awkward line breaks.

--------------------------------

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'mask' option allows for creating reveal effects by wrapping each text unit (lines, words, or chars) in an additional element with 'overflow: clip'. These mask elements can be accessed via the instance's 'masks' array.

---

## GSAP Flip Inversion Matrix Math

*Context7 Library ID:* `/websites/gsap_v3`  
*Search Query:* `Flip matrix getBoundingClientRect deltaX deltaY scaleX scaleY fit`

### Flip Plugin Options

Source: https://gsap.com/docs/v3/Plugins/Flip/static.from%28%29

Configuration options for the GSAP Flip plugin.

```APIDOC
## Flip Plugin Options

### Description
This section details the various configuration options available for the GSAP Flip plugin.

### Parameters
#### Request Body Options
- **prune** (Boolean) - Optional - If `true`, Flip will remove any targets from the animation that match the previous state (position/size) in order to conserve resources. This requires a little more processing up-front, but it may improve performance during the animation when several get removed, plus it also makes staggering more intuitive since you may not want non-animating targets to be factored into the staggering. *(added in 3.9.0)*
- **scale** (Boolean) - Optional - By default, Flip will affect the `width` and `height` CSS properties to alter the size, but if you'd rather scale the element instead (typically better performance), set `scale: true`.
- **simple** (Boolean) - Optional - If `true`, Flip will skip the extra calculations that would be necessary to accommodate rotation/scale/skew in determining positions. It's like telling Flip "I promise that there aren't any rotated/scaled/skewed containers for the Flipping elements" which makes things faster. In most cases, the performance difference isn't noticeable, but if you're flipping a lot of elements it can help keep things snappy.
- **spin** (Boolean | Number | Function) - Optional - If `true`, the elements will spin an extra 360 degrees during the flip animation which makes it look a little more fun. Or you can define a number of full rotations, including a negative number, so `-1` would spin in the opposite direction once. If you provide a function, it will be called once for each target so that you can return whatever value you'd like for each individual element's spin. This allows you to, for example, have certain targets spin one direction, other elements spin another direction, or return 0 to not spin at all.
- **targets** (String | Element | Array | NodeList) - Optional - By default, Flip will use the targets from the `state` object (first parameter), but you can specify a subset of those as either selector text (`".class, #id"`), an Element, an Array of Elements, or a NodeList. If any of the targets provided is NOT found in the `state` object, it will be passed to the `onEnter` and *not* included in the flip animation because there's no previous state from which to pull position/size data.

### Request Example
```javascript
Flip.from(state, {
  prune: true,
  scale: true,
  simple: true,
  spin: 1,
  targets: ".my-class"
});
```

### Request Example with Spin Function
```javascript
Flip.from(state, {
  spin: (index, target) => {
    if (target.classList.contains("clockwise")) {
      return 1;
    } else if (target.classList.contains("counter-clockwise")) {
      return -1;
    } else {
      return 0;
    }
  }
});
```
```

--------------------------------

### Flip.fit

Source: https://gsap.com/docs/v3/Plugins/Flip

Repositions or resizes an element to match the area of another target.

```APIDOC
## Flip.fit

### Description
Repositions/resizes one element so that it appears to fit exactly into the same area as another element.

### Parameters
#### Path Parameters
- **targetToResize** (String | Element) - Required - The element to be resized/repositioned.
- **destinationTargetOrState** (String | Element | FlipState) - Required - The target or state to match.
- **vars** (Object) - Required - Configuration object (e.g., scale: true, fitChild).
```

### Modifiers > Caveats

Source: https://gsap.com/docs/v3/GSAP/CorePlugins/Modifiers

When modifying CSS transform properties like `scale`, use `scaleX` and `scaleY` instead of `scale` (as `scale` is a shortcut for those). Similarly, use `rotation` and not `rotationZ` for the rotation property.

--------------------------------

### Flip.from

Source: https://gsap.com/docs/v3/Plugins/Flip/static.from%28%29

Flip.from immediately moves or resizes targets to match a provided state object and then animates them backwards to their current state. By default, the method uses width and height properties for resizing, but users can enable scaling via transforms by setting scale to true. The method returns a timeline animation, allowing for further control or the addition of other animations.

--------------------------------

### Flip > Configuration > scale

Source: https://gsap.com/docs/v3/Plugins/Flip

By default, Flip adjusts width and height properties to change element size. Setting scale to true enables the use of CSS scaling instead, which typically offers better performance during animations.

---

## Three.js WebGL State & Program Cache

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `WebGLState WebGLProgram useProgram shader compilation needsUpdate`

### Triggering material shader recompilation

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/how-to-update-things.html

Set needsUpdate to true when changing material properties that require a new shader program, such as adding textures or fog.

```javascript
material.needsUpdate = true
```

--------------------------------

### .compileAsync( scene : Object3D, camera : Camera, targetScene : Scene ) : Promise (async)

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/Renderer.html.md

Compiles all materials in the given scene. This can be useful to avoid a phenomenon which is called "shader compilation stutter", which occurs when rendering an object with a new shader for the first time. If you want to add a 3D object to an existing scene, use the third optional parameter for applying the target scene. Note that the (target) scene's lighting and environment must be configured before calling this method.

```APIDOC
## .compileAsync( scene : Object3D, camera : Camera, targetScene : Scene ) : Promise (async)

### Description
Compiles all materials in the given scene. This can be useful to avoid a phenomenon which is called "shader compilation stutter", which occurs when rendering an object with a new shader for the first time. If you want to add a 3D object to an existing scene, use the third optional parameter for applying the target scene. Note that the (target) scene's lighting and environment must be configured before calling this method.

### Parameters
- **scene** (Object3D) - Required - The scene or 3D object to precompile.
- **camera** (Camera) - Required - The camera that is used to render the scene.
- **targetScene** (Scene) - Optional - If the first argument is a 3D object, this parameter must represent the scene the 3D object is going to be added. Default is `null`.

### Returns
- (Promise) - A Promise that resolves when the compile has been finished.
```

--------------------------------

### .compileAsync( scene : Object3D, camera : Camera, targetScene : Scene )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html.md

Asynchronous version of `WebGLRenderer#compile`. This method makes use of the `KHR_parallel_shader_compile` WebGL extension. Hence, it is recommended to use this version of `compile()` whenever possible.

```APIDOC
## .compileAsync( scene : Object3D, camera : Camera, targetScene : Scene )

### Description
Asynchronous version of `WebGLRenderer#compile`. This method makes use of the `KHR_parallel_shader_compile` WebGL extension. Hence, it is recommended to use this version of `compile()` whenever possible.

### Parameters
- **scene** (Object3D) - The scene or another type of 3D object to precompile.
- **camera** (Camera) - The camera.
- **targetScene** (Scene) - Default: `null` - The target scene.

### Returns
- (Promise) - A Promise that resolves when the given scene can be rendered without unnecessary stalling due to shader compilation.
```

--------------------------------

### .compile

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html

Compiles all materials in a scene with a camera, useful for precompiling shaders.

```APIDOC
## .compile

### Description
Compiles all materials in the scene with the camera. This is useful to precompile shaders before the first rendering. If you want to add a 3D object to an existing scene, use the third optional parameter for applying the target scene. Note that the (target) scene's lighting and environment must be configured before calling this method.

### Method Signature
compile( scene : Object3D, camera : Camera, targetScene : Scene )

### Parameters
- **scene** (Object3D) - The scene or another type of 3D object to precompile.
- **camera** (Camera) - The camera.
- **targetScene** (Scene) - Default: `null` - The target scene.

### Return Value
Set.<Material> - The precompiled materials.
```

--------------------------------

### .onBeforeCompile( shaderobject : Object, renderer : WebGLRenderer )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/Material.html

An optional callback executed before shader compilation, useful for modifying built-in materials.

```APIDOC
## Method: .onBeforeCompile( shaderobject : Object, renderer : WebGLRenderer )

### Description
An optional callback that is executed immediately before the shader program is compiled. This function is called with the shader source code as a parameter. Useful for the modification of built-in materials.

This method can only be used when rendering with [WebGLRenderer](WebGLRenderer.html). The recommended approach when customizing materials is to use `WebGPURenderer` with the new Node Material system and [TSL](https://github.com/mrdoob/three.js/wiki/Three.js-Shading-Language).

### Parameters
- **shaderobject** (Object) - The object holds the uniforms and the vertex and fragment shader source.
- **renderer** (WebGLRenderer) - A reference to the renderer.

### Returns
(None)
```

---

## Three.js BufferAttribute & Vertex Layout

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `BufferAttribute Float32Array position normal uv index TorusGeometry`

### Set BufferGeometry Attributes

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/custom-buffergeometry.html

Configures the position, normal, and UV attributes for the geometry. Each attribute uses a BufferAttribute to wrap the data.

```javascript
geometry.setAttribute(
    'position',
    new THREE.BufferAttribute(positions, positionNumComponents));
geometry.setAttribute(
    'normal',
    new THREE.BufferAttribute(normals, normalNumComponents));
geometry.setAttribute(
    'uv',
    new THREE.BufferAttribute(uvs, uvNumComponents));
```

--------------------------------

### Populate TypedArrays for BufferGeometry Attributes

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/custom-buffergeometry-cube-typedarrays.html

Initializes Float32Array instances for positions, normals, and UVs, then iterates through the defined 'vertices' array to populate these typed arrays. This prepares the raw data for THREE.BufferAttribute.

```javascript
const numVertices = vertices.length;\nconst positionNumComponents = 3;\nconst normalNumComponents = 3;\nconst uvNumComponents = 2;\n\nconst positions = new Float32Array( numVertices * positionNumComponents );\nconst normals = new Float32Array( numVertices * normalNumComponents );\nconst uvs = new Float32Array( numVertices * uvNumComponents );\n\nlet posNdx = 0;\nlet nrmNdx = 0;\nlet uvNdx = 0;\n\nfor ( const vertex of vertices ) {\n  positions.set( vertex.pos, posNdx );\n  normals.set( vertex.norm, nrmNdx );\n  uvs.set( vertex.uv, uvNdx );\n  posNdx += positionNumComponents;\n  nrmNdx += normalNumComponents;\n  uvNdx += uvNumComponents;\n}
```

--------------------------------

### Create THREE.BufferGeometry with Attributes and Indices

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/custom-buffergeometry-cube-typedarrays.html

Instantiates a THREE.BufferGeometry and assigns the prepared TypedArrays as attributes for position, normal, and UV data. It also sets the index array to define the triangles that form the cube's faces.

```javascript
const geometry = new THREE.BufferGeometry();\ngeometry.setAttribute( 'position', new THREE.BufferAttribute( positions, positionNumComponents ) );\ngeometry.setAttribute( 'normal', new THREE.BufferAttribute( normals, normalNumComponents ) );\ngeometry.setAttribute( 'uv', new THREE.BufferAttribute( uvs, uvNumComponents ) );\ngeometry.setIndex( [\n  0, 1, 2,   2, 1, 3,  // front\n  4, 5, 6,   6, 5, 7,  // right\n  8, 9, 10,  10, 9, 11, // back\n  12, 13, 14, 14, 13, 15, // left\n  16, 17, 18, 18, 17, 19, // top\n  20, 21, 22, 22, 21, 23, // bottom\n] );
```

--------------------------------

### new Float32BufferAttribute( array : Array.<number> | Float32Array, itemSize : number, normalized : boolean )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/Float32BufferAttribute.html.md

Constructs a new buffer attribute.

```APIDOC
## Constructor: Float32BufferAttribute

### Description
Constructs a new buffer attribute.

### Signature
new Float32BufferAttribute( array : Array.<number> | Float32Array, itemSize : number, normalized : boolean )

### Parameters
- **array** (Array.<number> | Float32Array) - Required - The array holding the attribute data.
- **itemSize** (number) - Required - The item size.
- **normalized** (boolean) - Optional (Default: false) - Whether the data are normalized or not.
```

### Custom BufferGeometry > Attributes and Data Types

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/custom-buffergeometry.html

When creating a custom BufferGeometry, attribute names must match what three.js expects, such as position, normal, uv, or color, unless using a custom shader. Each attribute is defined by a BufferAttribute, which requires a TypedArray, such as a Float32Array, rather than a standard JavaScript array. Additionally, you must specify the number of components per vertex for each attribute, such as three for positions and normals or two for UV coordinates.

---

## Three.js PBR Microfacet & Cook-Torrance BRDF

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `MeshStandardMaterial roughness metalness GGX Cook-Torrance Fresnel PMREM`

### Initialize Three.js Scene with PMREM Cubemap and HDR Environment

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_pmrem_cubemap.html

This snippet sets up a Three.js WebGL scene, loads an HDR cubemap, generates a PMREM texture from it, and applies it as an environment map to multiple spheres with varying roughness and metalness.

```javascript
import * as THREE from 'three';
import { HDRCubeTextureLoader } from 'three/addons/loaders/HDRCubeTextureLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let camera, scene, renderer;

init();

async function init() {
	const container = document.createElement( 'div' );
	document.body.appendChild( container );
	camera = new THREE.PerspectiveCamera( 45, window.innerWidth / window.innerHeight, 0.25, 20 );
	camera.position.set( 0, 0, 8 );
	scene = new THREE.Scene();
	renderer = new THREE.WebGLRenderer( { antialias: true } );
	renderer.setPixelRatio( window.devicePixelRatio );
	renderer.setSize( window.innerWidth, window.innerHeight );
	renderer.setAnimationLoop( render );
	renderer.toneMapping = THREE.ACESFilmicToneMapping;
	container.appendChild( renderer.domElement );
	const controls = new OrbitControls( camera, renderer.domElement );
	controls.minDistance = 2;
	controls.maxDistance = 10;
	controls.update();
	new HDRCubeTextureLoader()
		.setPath( './textures/cube/pisaHDR/' )
		.load( [ 'px.hdr', 'nx.hdr', 'py.hdr', 'ny.hdr', 'pz.hdr', 'nz.hdr' ], function ( map ) {
			const pmremGenerator = new THREE.PMREMGenerator( renderer );
			const envMap = pmremGenerator.fromCubemap( map ).texture;
			scene.background = envMap;
			scene.backgroundBlurriness = 0.5;
			pmremGenerator.dispose();
			const geometry = new THREE.SphereGeometry( 0.4, 64, 64 );
			for ( let i = 0; i < 6; i ++ ) {
				for ( let j = 0; j < 5; j ++ ) {
					const material = new THREE.MeshPhysicalMaterial( {
						roughness: i / 5,
						metalness: j / 4,
						envMap: envMap
					} );
					const mesh = new THREE.Mesh( geometry, material );
					mesh.position.x = i - 2.5;
					mesh.position.y = j - 2;
					scene.add( mesh );
				}
			}
		} );
	window.addEventListener( 'resize', onWindowResize );
}

function onWindowResize() {
	camera.aspect = window.innerWidth / window.innerHeight;
	camera.updateProjectionMatrix();
	renderer.setSize( window.innerWidth, window.innerHeight );
}

// function render() {
	renderer.render( scene, camera );
// }
```

--------------------------------

### Using PMREMNode with MeshStandardNodeMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/PMREMNode.html

This snippet demonstrates how to assign a PMREM texture to the envNode property of a MeshStandardNodeMaterial.

```javascript
const material = new MeshStandardNodeMaterial();
material.envNode = pmremTexture( envMap );
```

--------------------------------

### .metalnessNode

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/SSRNode.html

Per-pixel metalness, used to drive the GGX reflection sampling and the non-metal early-out. When `null`, the shader treats surfaces as non-metallic.

```APIDOC
## .metalnessNode : Node.<float>

### Description
Per-pixel metalness, used to drive the GGX reflection sampling and the non-metal early-out. When `null`, the shader treats surfaces as non-metallic.

### Type
Node.<float>
```

### Materials > MeshStandardMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/materials.html

MeshStandardMaterial uses roughness and metalness settings rather than shininess. Roughness (0 to 1) is the opposite of shininess, where high roughness results in soft reflections like a baseball. Metalness (0 to 1) determines how metallic the material behaves, as metals reflect light differently than non-metals.

--------------------------------

### PMREMGenerator

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/PMREMGenerator.html.md

Unlike traditional mipmaps, PMREM only goes down to LOD_MIN, then creates extra filtered 'mips' at the same resolution for higher roughness levels, maintaining resolution for diffuse lighting. The prefiltering uses GGX VNDF importance sampling to generate environment maps that accurately match the GGX BRDF for physically-based image-based lighting.

---

## Three.js Context Loss & WebGL Resource Lifecycle

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `webglcontextlost webglcontextrestored initGLContext info autoReset`

### WebGLRenderer context lost/restored events and dispose

Source: https://github.com/mrdoob/three.js/blob/dev/src/renderers/WebGLRenderer.js

Registers webglcontextlost/restored listeners; onContextLost sets _isContextLost=true, onContextRestore reinitializes GL state; dispose removes listeners and cleans up all subsystems.

```javascript
			canvas.addEventListener( 'webglcontextlost', onContextLost, false );
			canvas.addEventListener( 'webglcontextrestored', onContextRestore, false );
			canvas.addEventListener( 'webglcontextcreationerror', onContextCreationError, false );

	this.dispose = function () {

		canvas.removeEventListener( 'webglcontextlost', onContextLost, false );
		canvas.removeEventListener( 'webglcontextrestored', onContextRestore, false );
		canvas.removeEventListener( 'webglcontextcreationerror', onContextCreationError, false );

		background.dispose();
		renderLists.dispose();
		renderStates.dispose();
		properties.dispose();
		environments.dispose();
		objects.dispose();
		bindingStates.dispose();
		uniformsGroups.dispose();
		programCache.dispose();

		xr.dispose();

		xr.removeEventListener( 'sessionstart', onXRSessionStart );
		xr.removeEventListener( 'sessionend', onXRSessionEnd );

		animation.stop();

	};

	function onContextLost( event ) {

		event.preventDefault();

		log( 'WebGLRenderer: Context Lost.' );

		_isContextLost = true;

	}

	function onContextRestore( /* event */ ) {

		log( 'WebGLRenderer: Context Restored.' );

		_isContextLost = false;

		const infoAutoReset = info.autoReset;
		const shadowMapEnabled = shadowMap.enabled;
		const shadowMapAutoUpdate = shadowMap.autoUpdate;
		const shadowMapNeedsUpdate = shadowMap.needsUpdate;
		const shadowMapType = shadowMap.type;

		initGLContext();

		info.autoReset = infoAutoReset;
		shadowMap.enabled = shadowMapEnabled;
		shadowMap.autoUpdate = shadowMapAutoUpdate;
		shadowMap.needsUpdate = shadowMapNeedsUpdate;
		shadowMap.type = shadowMapType;

	}
```

--------------------------------

### WebGLRenderer.Info.autoReset

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html.md

Controls whether the renderer automatically resets its info object each frame.

```APIDOC
## WebGLRenderer.Info.autoReset

### Description
Whether to automatically reset the info by the renderer or not.

Default is `true`.

### Type
boolean
```

--------------------------------

### Disable Automatic Info Reset for WebGLRenderer

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html

Sets the renderer's info statistics to not automatically reset after each render call, useful for custom reset patterns.

```javascript
renderer.info.autoReset = false;
```

--------------------------------

### WebGLRenderer.Info.reset()

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html.md

Resets the renderer's info object, typically for the next frame.

```APIDOC
## WebGLRenderer.Info.reset()

### Description
Resets the info object for the next frame.

### Type
function
```

### WebGLRenderer > Info

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html.md

WebGLRenderer Info provides runtime statistics and diagnostic information about the renderer's operations. It includes details on allocated memory for geometries and textures, as well as rendering statistics such as the frame ID, number of draw calls, and counts of rendered triangles, points, and lines per frame. The autoReset property controls whether this information is automatically cleared for each new frame.

---

