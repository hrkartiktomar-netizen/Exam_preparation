# Deep-Dive Technical Research Manual (Frontend Libraries)

> **Authoritative Source:** Context7 MCP (`https://mcp.context7.com/mcp`)
> **Generated On:** 2026-08-31T20:31:26.145Z
> **Objective:** Deep-dive analysis into physics, internal math, performance limits, edge cases, and memory lifecycles for Lenis, GSAP, and Three.js.

---

## Lenis Internal Physics & Damp

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `Lenis damp physics deltaTime frame rate independent velocity direction animatedScroll`

### raf → advance → onUpdate: the per-frame update cycle

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/core/src/lenis.ts

When lenis.raf is called, this.animate.advance computes the new interpolated value and calls onUpdate, which sets animatedScroll, immediately calls setScroll to push the real scrollbar, and emits the Lenis scroll event — all synchronously in one call stack. setScroll triggers a native scroll event, but onNativeScroll's guard (line 902) ensures it's a no-op during 'smooth' mode. No intentional deferral of any listener.

```typescript
  raf = (time: number) => {
    const deltaTime = time - (this.time || time)
    this.time = time

    this.animate.advance(deltaTime * 0.001)

    if (this.options.autoRaf) {
      this._rafId = requestAnimationFrame(this.raf)
    }
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

### Setup Lenis with custom requestAnimationFrame loop

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Manual integration of Lenis into a custom animation frame loop.

```js
// Initialize Lenis
const lenis = new Lenis();

// Use requestAnimationFrame to continuously update the scroll
function raf(time) {
  lenis.raf(time);
  requestAnimationFrame(raf);
}

requestAnimationFrame(raf);
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

---

## Lenis Nested Scroll & Prevent

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `Lenis allowNestedScroll prevent data-lenis-prevent wrapper touch overscroll iOS Safari`

### Prevent Scroll via JavaScript

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Use the prevent callback in the Lenis constructor to programmatically exclude specific DOM nodes from smooth scrolling.

```html
<div id="modal">scrollable content</div>
```

```js
const lenis = new Lenis({
  prevent: (node) => node.id === 'modal',
})
```

--------------------------------

### Prevent Scroll via HTML Attributes

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Apply data-lenis-prevent attributes to elements to disable smooth scrolling for specific containers.

```html
<div data-lenis-prevent>scrollable content</div>
```

--------------------------------

### Enable Nested Scrolling

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Use the allowNestedScroll option to enable native scrolling for nested elements, though this may impact performance.

```js
const lenis = new Lenis({
  allowNestedScroll: true,
})
```

--------------------------------

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

### Considerations > Nested scroll

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Handling nested scrollable elements can be achieved via the allowNestedScroll option, which automatically detects and enables native scrolling for nested elements. Because this requires checking the DOM tree on every scroll event, it may impact performance. For better performance, developers can use HTML attributes like data-lenis-prevent or define a custom prevent function in the Lenis configuration to target specific nodes.

---

## Lenis Virtual Scroll & Event Interception

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `Lenis virtualScroll callback deltaX deltaY onVirtualScroll emit`

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

### Events

Source: https://github.com/darkroomengineering/lenis/blob/main/README.md

Lenis provides event hooks for scroll interactions. The scroll event returns the current Lenis instance, while the virtual-scroll event provides an object containing deltaX, deltaY, and the original event.

---

## Lenis Snap & Horizontal Scroll

*Context7 Library ID:* `/darkroomengineering/lenis`  
*Search Query:* `Lenis snap mandatory proximity lock orientation horizontal gestureOrientation`

### Lenis Snap Initialization and Configuration

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/snap/README.md

How to initialize the Snap instance with a Lenis object and configure its behavior.

```APIDOC
## Initialization

### Description
Initializes the Snap instance to enable scroll snapping on a Lenis instance.

### Parameters
- **lenis** (Lenis) - Required - The Lenis instance to attach snapping to.
- **options** (Object) - Optional - Configuration object for snap behavior.

### Options
- **type** (string) - Optional - 'proximity' (default), 'mandatory', or 'lock'.
- **distanceThreshold** (string|number) - Optional - Distance from snap point to trigger snap (default: '50%').
- **debounce** (number) - Optional - Debounce time in ms (default: 500).
- **onSnapStart** (function) - Optional - Callback when snap starts.
- **onSnapComplete** (function) - Optional - Callback when snap completes.
- **lerp** (number) - Optional - Lerp value for snapping.
- **easing** (function) - Optional - Easing function for snapping.
- **duration** (number) - Optional - Duration for snapping.

### Request Example
```javascript
const snap = new Snap(lenis, {
  type: 'lock',
  distanceThreshold: '100%',
  debounce: 0
})
```
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

### Configure slideshow snap behavior

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/snap/README.md

Initialize a snap instance with lock type for slideshow-like navigation.

```jsx
    const snap = new Snap(lenis, {
      type: 'lock',
      distanceThreshold: '100%',
      debounce: 0,
    })
```

--------------------------------

### Snap Methods

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/snap/README.md

Methods available on the Snap instance to manage snap points and navigation.

```APIDOC
## Snap Methods

### Description
Methods to programmatically add snap points, navigate between them, and control the snap engine.

### Methods
- **add(value: number)** - Add a specific pixel value as a snap point.
- **addElement(element: HTMLElement, options: Object)** - Add an element as a snap target.
- **addElements(elements: HTMLElement[], options: Object)** - Add multiple elements as snap targets.
- **next()** - Navigate to the next snap point.
- **previous()** - Navigate to the previous snap point.
- **goTo(index: number)** - Navigate to a specific snap point index.
- **start()** - Enable the snap functionality.
- **stop()** - Disable the snap functionality.
- **resize()** - Recalculate snap point positions.
```

### lenis/snap > Options

Source: https://github.com/darkroomengineering/lenis/blob/main/packages/snap/README.md

The snap behavior can be configured using several options. The type can be set to proximity, mandatory, or lock. Other settings include distanceThreshold for defining how close the scroll must be to a snap point, debounce for timing, and various callbacks like onSnapStart and onSnapComplete to handle events during the snapping process.

---

## GSAP Ticker & LagSmoothing

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `gsap.ticker lagSmoothing add remove delta time fps clamp`

### clamp(min, max, value?)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-utils/SKILL.md

Constrains a value between a specified minimum and maximum. If the 'value' argument is omitted, it returns a function that accepts the value later.

```APIDOC
## gsap.utils.clamp

### Description
Constrains a value between min and max. Omit 'value' to get a function: `clamp(min, max)(value)`.

### Parameters
- **min** (number) - The minimum allowed value.
- **max** (number) - The maximum allowed value.
- **value** (number, optional) - The value to clamp.

### Returns
- (number) The clamped value, or a function that accepts a value and returns the clamped result.

### Examples
```javascript
// Returns the clamped value
gsap.utils.clamp(0, 100, 150); // 100
gsap.utils.clamp(0, 100, -10); // 0

// Returns a function that clamps values
let clampFn = gsap.utils.clamp(0, 100);
clampFn(150); // 100
clampFn(-10); // 0
```
```

--------------------------------

### GSAP Utils: Clamp with and without value

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-utils/SKILL.md

Demonstrates how `gsap.utils.clamp` can be used to constrain a value within a specified range, either by providing the value directly or by creating a reusable function.

```javascript
gsap.utils.clamp(0, 100, 150);

let c = gsap.utils.clamp(0, 100);
c(150);
```

### gsap.utils > Clamping and Ranges > clamp(min, max, value?)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-utils/SKILL.md

The `clamp(min, max, value?)` utility constrains a numerical value to be within a specified minimum and maximum range. If the `value` argument is omitted, it returns a function that accepts the value to be clamped.

---

## GSAP Context & Scoping

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `gsap.context revert add scope cleanup memory management`

### gsap.context() in useEffect for Cleanup

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-react/SKILL.md

Use gsap.context() within a useEffect hook when not using useGSAP. Ensure you return ctx.revert() in the cleanup function to prevent memory leaks and issues with detached DOM nodes.

```javascript
import { useEffect, useRef } from "react";

const containerRef = useRef(null);

useEffect(() => {
  const ctx = gsap.context(() => {
    gsap.to(".box", { x: 100 });
    gsap.from(".item", { opacity: 0, stagger: 0.1 });
  }, containerRef);
  return () => ctx.revert();
}, []);
```

--------------------------------

### Context-Safe Callbacks with useGSAP

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-react/SKILL.md

Use `contextSafe` to ensure GSAP animations created within event handlers are properly managed and reverted by GSAP's context. This prevents memory leaks and ensures animations are cleaned up on component unmount or re-render.

```javascript
const container = useRef();
const badRef = useRef();
const goodRef = useRef();

useGSAP((context, contextSafe) => {
	// ✅ safe, created during execution
	gsap.to(goodRef.current, { x: 100 });

	// ❌ DANGER! This animation is created in an event handler that executes AFTER useGSAP() executes. It's not added to the context so it won't get cleaned up (reverted). The event listener isn't removed in cleanup function below either, so it persists between component renders (bad).
	badRef.current.addEventListener('click', () => {
		gsap.to(badRef.current, { y: 100 });
	});

	// ✅ safe, wrapped in contextSafe() function
	const onClickGood = contextSafe(() => {
		gsap.to(goodRef.current, { rotation: 180 });
	});

	goodRef.current.addEventListener('click', onClickGood);

	// 👍 we remove the event listener in the cleanup function below.
	return () => {
		// <-- cleanup
		goodRef.current.removeEventListener('click', onClickGood);
	};
},{ scope: container });
```

--------------------------------

### Scope GSAP Selectors with gsap.context()

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-frameworks/SKILL.md

Pass the container element or ref as the second argument to gsap.context() to limit selector searches to that subtree. This prevents unintended matches outside the current component.

```javascript
gsap.context(() => {
  gsap.to(".box", { x: 100 });
}, containerRef);
```

--------------------------------

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

### Do Not

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-react/SKILL.md

Avoid targeting elements using selector strings without a defined `scope`. Always pass a `scope` (which can be a ref or an element) to `useGSAP` or `gsap.context()`. This ensures that selectors like `.box` are confined to the component's root element and do not inadvertently select elements outside of it. Similarly, do not skip the cleanup process; always revert the context or explicitly kill any tweens or ScrollTriggers in the effect's return function to prevent memory leaks and issues with updates on unmounted nodes.

---

## GSAP ScrollTrigger ScrollerProxy & Pinning

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `ScrollTrigger scrollerProxy pinType fixed transform pinSpacing anticipatePin`

### ScrollTrigger.scrollerProxy()

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Overrides how ScrollTrigger reads and writes scroll position for a given scroller. Essential for integrating with third-party smooth-scrolling libraries.

```APIDOC
## ScrollTrigger.scrollerProxy()

### Description
Overrides how ScrollTrigger reads and writes scroll position for a given scroller. Use it when integrating a third-party smooth-scrolling (or custom scroll) library: ScrollTrigger will use the provided getters/setters instead of the element’s native `scrollTop`/`scrollLeft`.

### Method Signature
`ScrollTrigger.scrollerProxy(scroller, vars)`

### Parameters
- **scroller**: selector or element (e.g. `"body"`, `".container"`).
- **vars**: object with **scrollTop** and/or **scrollLeft** functions. Each acts as getter and setter: when called **with** an argument, it is a setter; when called **with no** argument, it returns the current value (getter). At least one of **scrollTop** or **scrollLeft** is required.

### Optional vars
- **getBoundingClientRect** (Function): Returns `{ top, left, width, height }` for the scroller. Needed when the scroller’s real rect is not the default.
- **scrollWidth** / **scrollHeight** (Getter/setter functions): When the library exposes different dimensions.
- **fixedMarkers** (Boolean): When `true`, markers are treated as `position: fixed`. Useful when the scroller is translated.
- **pinType** (String): Controls how pinning is applied. Use `"fixed"` if pins jitter; use `"transform"` if pins do not stick.

### Critical Note
When the third-party scroller updates its position, ScrollTrigger must be notified. Register **ScrollTrigger.update** as a listener (e.g. `smoothScroller.addListener(ScrollTrigger.update)`). Without this, ScrollTrigger’s calculations will be out of date.

### Request Example
```javascript
// Example: proxy body scroll to a third-party scroll instance
ScrollTrigger.scrollerProxy(document.body, {
  scrollTop(value) {
    if (arguments.length) scrollbar.scrollTop = value;
    return scrollbar.scrollTop;
  },
  getBoundingClientRect() {
    return { top: 0, left: 0, width: window.innerWidth, height: window.innerHeight };
  }
});
scrollbar.addListener(ScrollTrigger.update);
```
```

--------------------------------

### Proxy Body Scroll for Third-Party Libraries

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Use ScrollTrigger.scrollerProxy() to integrate GSAP ScrollTrigger with third-party scrolling libraries. This example proxies the body's scroll position to a custom scrollbar instance.

```javascript
// Example: proxy body scroll to a third-party scroll instance
ScrollTrigger.scrollerProxy(document.body, {
  scrollTop(value) {
    if (arguments.length) scrollbar.scrollTop = value;
    return scrollbar.scrollTop;
  },
  getBoundingClientRect() {
    return { top: 0, left: 0, width: window.innerWidth, height: window.innerHeight };
  }
});
scrollbar.addListener(ScrollTrigger.update);
```

--------------------------------

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

### ScrollTrigger.scrollerProxy() > vars

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

When configuring ScrollTrigger.scrollerProxy(), you provide 'scrollTop' and/or 'scrollLeft' functions that act as both getters and setters. Additionally, optional vars include 'getBoundingClientRect' for the scroller's dimensions, 'scrollWidth'/'scrollHeight' getters/setters if the library exposes different dimensions, 'fixedMarkers' to handle fixed positioning of markers, and 'pinType' ('fixed' or 'transform') to control how pinning is applied.

--------------------------------

### Key config options

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

The `pin` property allows an element to be fixed in place while the ScrollTrigger is active. Setting it to `true` pins the trigger element itself. It's recommended to animate child elements rather than the pinned element directly. `pinSpacing` defaults to `true`, adding a spacer to prevent layout collapse.

---

## GSAP ScrollTrigger Batch & Snapping

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `ScrollTrigger.batch ScrollTrigger snap snapTo duration ease markers`

### ScrollTrigger.batch()

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Creates ScrollTriggers for multiple targets and batches their callbacks. Useful for coordinating animations on elements entering the viewport simultaneously.

```APIDOC
## ScrollTrigger.batch()

### Description
Creates one ScrollTrigger per target and batches their callbacks (onEnter, onLeave, etc.) within a short interval. Use it to coordinate an animation (e.g. with staggers) for all elements that fire a similar callback around the same time.

### Method Signature
`ScrollTrigger.batch(triggers, vars)`

### Parameters
- **triggers**: selector text (e.g. `".box"`) or Array of elements.
- **vars**: standard ScrollTrigger config (start, end, once, callbacks, etc.). Do **not** pass `trigger` (targets are the triggers) or animation-related options: `animation`, `invalidateOnRefresh`, `onSnapComplete`, `onScrubComplete`, `scrub`, `snap`, `toggleActions`.

### Batch Options in vars
- **interval** (Number): Max time in seconds to collect each batch. Default is roughly one requestAnimationFrame. When the first callback of a type fires, the timer starts; the batch is delivered when the interval elapses or when **batchMax** is reached.
- **batchMax** (Number | Function): Max elements per batch. When full, the callback fires and the next batch starts. Use a **function** that returns a number for responsive layouts; it runs on refresh (resize, tab focus, etc.).

### Callback Signature
Batched callbacks receive two parameters:
1. **targets** — Array of trigger elements that fired this callback within the interval.
2. **scrollTriggers** — Array of the ScrollTrigger instances that fired. Use for progress, direction, or `kill()`.

### Request Example
```javascript
ScrollTrigger.batch(".box", {
  onEnter: (elements, triggers) => {
    gsap.to(elements, { opacity: 1, y: 0, stagger: 0.15 });
  },
  onLeave: (elements, triggers) => {
    gsap.to(elements, { opacity: 0, y: 100 });
  },
  start: "top 80%",
  end: "bottom 20%"
});
```

### Request Example with batchMax and interval
```javascript
ScrollTrigger.batch(".card", {
  interval: 0.1,
  batchMax: 4,
  onEnter: (batch) => gsap.to(batch, { opacity: 1, y: 0, stagger: 0.1, overwrite: true }),
  onLeaveBack: (batch) => gsap.set(batch, { opacity: 0, y: 50, overwrite: true })
});
```
```

--------------------------------

### Development Markers with ScrollTrigger

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

Displays visual markers for trigger start and end points during development. Set `markers: false` or remove the option for production environments.

```javascript
scrollTrigger: {
  trigger: ".box",
  start: "top center",
  end: "bottom center",
  markers: true
}
```

--------------------------------

### snap(snapTo, value?)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-utils/SKILL.md

Snaps a value to the nearest multiple of snapTo or to the nearest value in an array. Can be used directly or as a function generator.

```APIDOC
## snap(snapTo, value?)

### Description
Snaps a value to the nearest multiple of `snapTo`, or to the nearest value in an array of allowed values. Omit `value` to get a function: `snap(snapTo)(value)` (or `snap(snapArray)(value)`).

### Usage
```javascript
gsap.utils.snap(10, 23);     // 20
gsap.utils.snap(0.25, 0.7);  // 0.75
gsap.utils.snap([0, 100, 200], 150); // 100 or 200 (nearest in array)

let snapFn = gsap.utils.snap(10);
snapFn(23); // 20
```

### Example in Tweens
Use in tweens for grid or step-based animation:
```javascript
gsap.to(".x", { x: 200, snap: { x: 20 } });
```
```

--------------------------------

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

### Key config options

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-scrolltrigger/SKILL.md

The `snap` property enables snapping the animation to specific progress values. This can be configured with a number for increments (e.g., `0.25`), an array of specific values, the string 'labels' to snap to timeline labels, or an object for detailed control over snapping behavior, duration, delay, and easing.

---

## GSAP SplitText Masking & Accessibility

*Context7 Library ID:* `/greensock/gsap-skills`  
*Search Query:* `SplitText mask lines words overflow clip aria auto hidden smartWrap`

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

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'mask' option allows for creating reveal effects by wrapping each text unit (lines, words, or chars) in an additional element with 'overflow: clip'. These mask elements can be accessed via the instance's 'masks' array.

--------------------------------

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'aria' configuration option controls accessibility for split text. 'auto' (default) adds ARIA attributes to aid screen readers. 'hidden' hides all split elements from screen readers, and 'none' leaves ARIA attributes unchanged. Use 'none' if custom ARIA handling is required.

--------------------------------

### SplitText — key config (SplitText.create vars)

Source: https://github.com/greensock/gsap-skills/blob/main/skills/gsap-plugins/SKILL.md

The 'type' configuration option for SplitText determines what units to split the text into, with options including 'chars', 'words', and 'lines'. The default is 'chars,words,lines'. For performance, it's recommended to only split the units that are actually needed for animation. If splitting only characters, 'smartWrap: true' can prevent awkward line breaks.

---

## GSAP Flip Nested & Absolute Transitions

*Context7 Library ID:* `/websites/gsap_v3`  
*Search Query:* `Flip.from absoluteOnLeave nested scale spin fit props`

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

### Customizing Flip Animation with Spin Function

Source: https://gsap.com/docs/v3/Plugins/Flip

Use a function for the `spin` property to control individual element rotations during a flip animation. This allows for conditional spinning based on element properties or index.

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
  },
})
```

--------------------------------

### Flip.from() Configuration Options

Source: https://gsap.com/docs/v3/Plugins/Flip

Details the optional properties that can be included in the configuration object passed as the second parameter to the `Flip.from()` method. These options extend standard tween properties to provide advanced control over FLIP animations.

```APIDOC
## Flip.from() Configuration Options

The `Flip.from()` method accepts an options object as its second parameter. This object can include any standard tween properties (like `duration`, `ease`, `onComplete`) in addition to the following specific FLIP configuration properties:

### `absolute`

*   **Type**: Boolean | String | Array | NodeList | Element
*   **Description**: Specifies which targets should have `position: absolute` applied during the FLIP animation. If `true`, all targets are affected. You can also provide selector text, an Array, NodeList, or a single Element to affect a subset of targets. This is useful for complex layouts (flex, grid) and can solve layout challenges. Setting `absolute: true` can cause elements to be removed from the document flow, potentially collapsing the layout; consider using a subset if this is an issue.
*   **Added**: v3.9.0

### `absoluteOnLeave`

*   **Type**: Boolean
*   **Description**: If `true`, elements that are "leaving" (passed to the `onLeave` callback) will be set to `position: absolute` during the flip animation. This is beneficial when hiding elements (e.g., `display: none`) while still animating them out, ensuring they don't affect the layout during the animation.
*   **Added**: v3.9.0

### `fade`

*   **Type**: Boolean
*   **Description**: If `true`, elements associated with the same `data-flip-id` in the previous and end states will cross-fade instead of being swapped immediately. This only applies when swapping elements. If the leaving element is `display: none`, it won't be visible for fading unless `absolute: true` is also set, which forces the element to its previous display state during the flip.

### `nested`

*   **Type**: Boolean
*   **Description**: If `true`, Flip performs extra calculations to prevent compounding movements when animating nested targets (e.g., a parent and its child are both targets). Without this, a child's movement could be amplified by its parent's movement.

### `onEnter`

*   **Type**: Function
*   **Description**: A callback function executed when a target is present in the end state but was either not found in the original `state` or was not in the document flow (e.g., `display: none`). Since there's no original position/size data, it won't be part of the flip animation. The callback receives an Array of entering elements, allowing you to animate them (e.g., fade them in). Any animation returned by this callback is added to the flip timeline.
*   **Example**: `onEnter: elements => gsap.fromTo(elements, {opacity: 0}, {opacity: 1})`

### `onLeave`

*   **Type**: Function
*   **Description**: A callback function executed when a target is present in the original `state` but not the end state, or if it's not in the document flow in the end state (e.g., `display: none`). Since there's no end state position/size data, it won't be part of the flip animation. The callback receives an Array of leaving elements, allowing you to animate them (e.g., fade them out). For these elements to be visible, `absolute: true` must also be set. If `absolute: true` is used, the element's `display` property is temporarily restored during the flip.
*   **Example**: `onLeave: elements => gsap.fromTo(elements, {opacity: 1}, {opacity: 0})`

### `props`

*   **Type**: String (Array of strings)
*   **Description**: (Not fully described in source text, but typically used to specify which properties should be animated by FLIP.)

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

---

## GSAP Observer Velocity & Axis Lock

*Context7 Library ID:* `/websites/gsap_v3`  
*Search Query:* `Observer lockAxis velocityX velocityY tolerance dragMinimum`

### lockAxis Property

Source: https://gsap.com/docs/v3/Plugins/Draggable/lockAxis

The lockAxis property is a boolean that restricts movement to a single axis once dragging begins. It's applicable for Draggables with types like 'x,y', 'top,left', and 'scroll'.

```APIDOC
## lockAxis Property

### Description
Locks movement to one axis based on how it is moved initially.

### Details
* **lockAxis** (Boolean) - If `true`, dragging more than 2 pixels in either direction (horizontally or vertically) will lock movement into that axis so that the element can only be dragged that direction (horizontally or vertically, whichever had the most initial movement). No diagonal movement will be allowed. This is only applicable for `type: "x,y"` and `type: "top,left"` and `type: "scroll"` Draggables. If you only want to allow vertical movement, you should set the `type` to `"y"`, `"top"`, or `"scrollTop"`. If you only want to allow horizontal movement, you should set the `type` to `"x"`, `"left"`, or `"scrollLeft"`.
```

--------------------------------

### Observer Configuration Options

Source: https://gsap.com/docs/v3/Plugins/Observer

A comprehensive list of configuration properties and event callbacks for the GSAP Observer utility.

```APIDOC
## Observer Configuration

### Description
Configuration options and event callbacks for the GSAP Observer utility to track user interactions.

### Parameters
- **onMove** (Function) - Callback for pointer/mouse movement over the target.
- **onPress** (Function) - Callback for touch/pointer press down.
- **onRelease** (Function) - Callback for touch/pointer release.
- **onRight** (Function) - Callback for motion detected toward the right.
- **onStop** (Function) - Callback when changes cease for the duration of onStopDelay.
- **onStopDelay** (Number) - Seconds to wait before triggering onStop (default: 0.25).
- **onToggleX** (Function) - Callback when motion switches direction on the x-axis.
- **onToggleY** (Function) - Callback when motion switches direction on the y-axis.
- **onUp** (Function) - Callback when upward motion is detected.
- **onWheel** (Function) - Callback for mouse wheel usage.
- **scrollSpeed** (Number) - Multiplier for scroll delta values.
- **target** (Element | String) - The element to listen for events on (default: viewport).
- **tolerance** (Number) - Minimum distance in pixels to trigger movement callbacks.
- **type** (String) - Comma-delimited list of event types: "wheel,touch,scroll,pointer".
- **wheelSpeed** (Number) - Multiplier for wheel delta values.
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

### Property: lockedAxis

Source: https://gsap.com/docs/v3/Plugins/Draggable/lockedAxis

Retrieves the axis ('x' or 'y') that is currently locked during a drag operation.

```APIDOC
## Property: lockedAxis

### Description
The `lockedAxis` property returns the axis along which movement is locked during a specific drag interaction. It is populated after the Draggable instance determines the direction of the drag.

### Returns
- **String** - The axis that is locked ("x" or "y").

### Usage Example
```javascript
Draggable.create("#yourID", {
  type: "x,y",
  lockAxis: true,
  onLockAxis: function () {
    console.log("locked axis: " + this.lockedAxis);
  },
});
```
```

--------------------------------

### Monitor locked axis with onLockAxis callback

Source: https://gsap.com/docs/v3/Plugins/Draggable/lockedAxis

Use the onLockAxis callback to detect when the drag axis is locked and access the lockedAxis property.

```javascript
Draggable.create("#yourID", {
  type: "x,y",
  lockAxis: true,
  onLockAxis: function () {
    console.log("locked axis: " + this.lockedAxis);
  },
});
```

---

## Three.js Color Spaces & ToneMapping

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `WebGLRenderer outputColorSpace SRGBColorSpace ACESFilmicToneMapping AgXToneMapping pixelRatio`

### Setting Up WebGLRenderer, Controls, and Stats

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_modifier_tessellation.html

Configures the `WebGLRenderer`, sets its size, and attaches it to the DOM. It also initializes `TrackballControls` for camera interaction and `Stats` for performance monitoring.

```JavaScript
renderer = new THREE.WebGLRenderer( { antialias: true } ); renderer.setPixelRatio( window.devicePixelRatio ); renderer.setSize( WIDTH, HEIGHT ); renderer.setAnimationLoop( animate ); const container = document.getElementById( 'container' ); container.appendChild( renderer.domElement ); controls = new TrackballControls( camera, renderer.domElement ); stats = new Stats(); container.appendChild( stats.dom );
```

--------------------------------

### .outputColorSpace

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/SVGRenderer.html.md

The output color space. Default is `SRGBColorSpace`.

```APIDOC
## PROPERTY .outputColorSpace

### Description
The output color space.

### Type
SRGBColorSpace | LinearSRGBColorSpace

### Default
SRGBColorSpace
```

--------------------------------

### .setDrawingBufferSize( width : number, height : number, pixelRatio : number )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/CanvasTarget.html

This method allows to define the drawing buffer size by specifying width, height and pixel ratio all at once. The size of the drawing buffer is computed with this formula: size.x = width * pixelRatio; size.y = height * pixelRatio;

```APIDOC
## METHOD .setDrawingBufferSize()

### Description
This method allows to define the drawing buffer size by specifying width, height and pixel ratio all at once. The size of the drawing buffer is computed with this formula: size.x = width * pixelRatio; size.y = height * pixelRatio;

### Parameters
- **width** (number) - The width in logical pixels.
- **height** (number) - The height in logical pixels.
- **pixelRatio** (number) - The pixel ratio.
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

## Three.js Dynamic BufferGeometry Updates

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `BufferGeometry setAttribute position needsUpdate InstancedMesh count`

### Configuring BufferGeometry for Dynamic Position Updates

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/custom-buffergeometry-dynamic.html

Creates a `BufferGeometry` with generated positions, normals, and indices, explicitly setting the position attribute's usage to `THREE.DynamicDrawUsage` for efficient per-frame modifications.

```javascript
  const segmentsAround = 24;
  const segmentsDown = 16;
  const { positions, indices } = makeSpherePositions( segmentsAround, segmentsDown );
  const normals = positions.slice();

  const geometry = new THREE.BufferGeometry();

  const positionNumComponents = 3;
  const normalNumComponents = 3;

  const positionAttribute = new THREE.BufferAttribute( positions, positionNumComponents );
  positionAttribute.setUsage( THREE.DynamicDrawUsage );
  geometry.setAttribute( 'position', positionAttribute );
  geometry.setAttribute( 'normal', new THREE.BufferAttribute( normals, normalNumComponents ) );
  geometry.setIndex( indices );
```

--------------------------------

### Update BufferAttribute positions dynamically

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/custom-buffergeometry.html

Mark attributes as dynamic to hint frequent changes and set needsUpdate to true after modifying the underlying data array.

```javascript
const temp = new THREE.Vector3();

...

for (let i = 0; i < positions.length; i += 3) {
  const quad = (i / 12 | 0);
  const ringId = quad / segmentsAround | 0;
  const ringQuadId = quad % segmentsAround;
  const ringU = ringQuadId / segmentsAround;
  const angle = ringU \* Math.PI \* 2;
  temp.fromArray(normals, i);
  temp.multiplyScalar(THREE.MathUtils.lerp(1, 1.4, Math.sin(time + ringId + angle) \* .5 + .5));
  temp.toArray(positions, i);
}
positionAttribute.needsUpdate = true;
```

--------------------------------

### new InstancedMesh( geometry : BufferGeometry, material : Material | Array.<Material>, count : number )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/InstancedMesh.html.md

Constructs a new instanced mesh. This constructor initializes an `InstancedMesh` object, allowing for efficient rendering of multiple instances of the same geometry with different transformations.

```APIDOC
## Constructor: new InstancedMesh

### Description
Constructs a new instanced mesh. This constructor initializes an `InstancedMesh` object, allowing for efficient rendering of multiple instances of the same geometry with different transformations.

### Method Signature
`new InstancedMesh( geometry : BufferGeometry, material : Material | Array.<Material>, count : number )`

### Parameters
- **geometry** (BufferGeometry) - Required - The mesh geometry.
- **material** (Material | Array.<Material>) - Required - The mesh material.
- **count** (number) - Required - The number of instances.
```

### Custom BufferGeometry - Dynamic > Dynamic Updates

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/custom-buffergeometry-dynamic.html

For a BufferGeometry to be dynamically updated, its BufferAttribute (e.g., for positions) must have its usage set to THREE.DynamicDrawUsage. After modifying the underlying data array of the attribute, the needsUpdate property of that attribute must be set to true to inform Three.js to re-upload the updated data to the GPU for rendering.

--------------------------------

### Constructor

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/InstancedMesh.html

A new InstancedMesh is constructed by providing a BufferGeometry for the mesh geometry, a Material or an array of Materials for the mesh material, and a count representing the number of instances to be rendered.

---

## Three.js PBR Physics & PMREMGenerator

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `MeshStandardMaterial MeshPhysicalMaterial roughness metalness envMap PMREMGenerator`

### Loading Textures for Physical Materials

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgpu_lights_physical.html

Applying diffuse, bump, and roughness maps to MeshStandardMaterial for realistic surfaces.

```javascript
floorMat = new THREE.MeshStandardMaterial( { roughness: 0.8, color: 0xffffff, metalness: 0.2, bumpScale: 1 } ); const textureLoader = new THREE.TextureLoader(); textureLoader.load( 'textures/hardwood2_diffuse.jpg', function ( map ) { map.wrapS = THREE.RepeatWrapping; map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; map.repeat.set( 10, 24 ); map.colorSpace = THREE.SRGBColorSpace; floorMat.map = map; floorMat.needsUpdate = true; } ); textureLoader.load( 'textures/hardwood2_bump.jpg', function ( map ) { map.wrapS = THREE.RepeatWrapping; map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; map.repeat.set( 10, 24 ); floorMat.bumpMap = map; floorMat.needsUpdate = true; } ); textureLoader.load( 'textures/hardwood2_roughness.jpg', function ( map ) { map.wrapS = THREE.RepeatWrapping; map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; map.repeat.set( 10, 24 ); floorMat.roughnessMap = map; floorMat.needsUpdate = true; } ); cubeMat = new THREE.MeshStandardMaterial( { roughness: 0.7, color: 0xffffff, bumpScale: 1, metalness: 0.2 } ); textureLoader.load( 'textures/brick_diffuse.jpg', function ( map ) { map.wrapS = THREE.RepeatWrapping; map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; map.repeat.set( 1, 1 ); map.colorSpace = THREE.SRGBColorSpace; cubeMat.map = map; cubeMat.needsUpdate = true; } ); textureLoader.load( 'textures/brick_bump.jpg', function ( map ) { map.wrapS = THREE.RepeatWrapping; map.wrapT = THREE.RepeatWrapping; map.anisotropy = 4; map.repeat.set( 1, 1 ); cubeMat.bumpMap = map; cubeMat.needsUpdate = true; } ); ballMat = new THREE.MeshStandardMaterial( { color: 0xffffff, roughness: 0.5, metalness: 1.0 } ); textureLoader.load( 'textures/planets/earth_atmos_2048.jpg', function ( map ) { map.anisotropy = 4; map.colorSpace = THREE.SRGBColorSpace; ballMat.map = map; ballMat.needsUpdate = true; } ); textureLoader.load( 'textures/planets/earth_specular_2048.jpg', function ( map ) { map.anisotropy = 4; map.colorSpace = THREE.SRGBColorSpace; ballMat.metalnessMap = map; ballMat.needsUpdate = true; } );
```

--------------------------------

### Creating Physically Based Meshes with Environment Map

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_pmrem_equirectangular.html

Generates a grid of spheres using MeshPhysicalMaterial with varying roughness and metalness, applying the pre-processed environment map.

```javascript
const geometry = new THREE.SphereGeometry( 0.4, 64, 64 );
for ( let i = 0; i < 6; i ++ ) {
  for ( let j = 0; j < 5; j ++ ) {
    const material = new THREE.MeshPhysicalMaterial( { roughness: i / 5, metalness: j / 4, envMap: envMap } );
    const mesh = new THREE.Mesh( geometry, material );
    mesh.position.x = i - 2.5;
    mesh.position.y = j - 2;
    scene.add( mesh );
  }
}
```

--------------------------------

### .isMeshPhysicalNodeMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/MeshPhysicalNodeMaterial.html.md

This flag can be used for type testing to determine if an object is a MeshPhysicalNodeMaterial. It is a readonly boolean property.

```APIDOC
## .isMeshPhysicalNodeMaterial : boolean (readonly)

### Description
This flag can be used for type testing.

### Type
boolean

### Default
`true`

### Readonly
Yes
```

--------------------------------

### WebGPU White Furnace Test Application in three.js

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgpu_furnace_test.html

Initializes a three.js WebGPU renderer, sets up a scene with a camera, creates a grid of spheres with varying roughness and metalness, and renders the scene.

```javascript
import * as THREE from 'three'; import { GUI } from 'three/addons/libs/lil-gui.module.min.js'; let scene, camera, renderer, radianceMap; let gui; const COLOR = 0xcccccc; async function init() { const width = window.innerWidth; const height = window.innerHeight; const aspect = width / height; // renderer renderer = new THREE.WebGPURenderer( { antialias: true } ); renderer.setSize( width, height ); renderer.setPixelRatio( window.devicePixelRatio ); document.body.appendChild( renderer.domElement ); await renderer.init(); // scene scene = new THREE.Scene(); // camera camera = new THREE.PerspectiveCamera( 40, aspect, 1, 30 ); camera.position.set( 0, 0, 18 ); // initGui(); window.addEventListener( 'resize', onWindowResize ); } function createObjects() { const geometry = new THREE.SphereGeometry( 0.4, 32, 16 ); for ( let x = 0; x <= 10; x ++ ) { for ( let y = 0; y <= 10; y ++ ) { const material = new THREE.MeshPhysicalMaterial( { roughness: x / 10, metalness: y / 10, color: 0xffffff, envMap: radianceMap, envMapIntensity: 1, transmission: 0, ior: 1.5 } ); const mesh = new THREE.Mesh( geometry, material ); mesh.position.x = x - 5; mesh.position.y = 5 - y; scene.add( mesh ); } } } function createEnvironment() { const envScene = new THREE.Scene(); envScene.background = new THREE.Color( COLOR ); const pmremGenerator = new THREE.PMREMGenerator( renderer ); radianceMap = pmremGenerator.fromScene( envScene ).texture; pmremGenerator.dispose(); scene.background = envScene.background; } function onWindowResize() { const width = window.innerWidth; const height = window.innerHeight; camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize( width, height ); render(); } function render() { renderer.render( scene, camera ); } function initGui() { gui = new GUI(); const param = { 'tint': false }; gui.add( param, 'tint' ).name( 'Tint for Visibility' ).onChange( function ( val ) { scene.traverse( function ( child ) { const tint = val ? 0xccccff : 0xffffff; if ( child.isMesh ) child.material.color.setHex( tint ); } ); render(); } ); } Promise.resolve() .then( init ) .then( createEnvironment ) .then( createObjects ) .then( render );
```

### Materials > MeshStandardMaterial

Source: https://github.com/mrdoob/three.js/blob/dev/manual/pages/materials.html

MeshStandardMaterial uses roughness and metalness settings rather than shininess. Roughness (0 to 1) is the opposite of shininess, where high roughness results in soft reflections like a baseball. Metalness (0 to 1) determines how metallic the material behaves, as metals reflect light differently than non-metals.

---

## Three.js Comprehensive Disposal & Leak Prevention

*Context7 Library ID:* `/mrdoob/three.js`  
*Search Query:* `ResourceTracker disposeScene traverse geometry material texture WebGLRenderer context`

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

--------------------------------

### Dispose Three.js Scene Resources

Source: https://github.com/mrdoob/three.js/blob/dev/examples/webgl_loader_svg.html

Traverses a Three.js scene to dispose of geometries, materials, and textures for meshes and lines, releasing GPU memory.

```javascript
function disposeScene( scene ) { scene.traverse( function ( object ) { if ( object.isMesh || object.isLine ) { object.geometry.dispose(); if ( object.material.map ) object.material.map.dispose(); object.material.dispose(); } } ); }
```

--------------------------------

### .traverseCallback( node : Node )

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/TSL.html.md

Callback function for `Node#traverse`. This function is invoked for each node during a traversal operation.

```APIDOC
## .traverseCallback( node : Node )

### Description
Callback function for `Node#traverse`. This function is invoked for each node during a traversal operation.

### Parameters
- **node** (Node) - The current node being traversed.
```

### InfoMemory

Source: https://github.com/mrdoob/three.js/blob/dev/docs/pages/WebGLRenderer.html

The WebGLRenderer provides InfoMemory to track the number of active geometries and textures currently in use.

--------------------------------

### Cleanup Loaded Files > ResourceTracker Class > dispose Method

Source: https://github.com/mrdoob/three.js/blob/dev/manual/examples/cleanup-loaded-files.html

The dispose method is crucial for releasing memory held by tracked resources. It iterates through all resources managed by the ResourceTracker, removing Object3D instances from their parents and calling the dispose() method on other disposable resources like geometries, materials, and textures. After disposal, the tracker's resource list is cleared.

---

