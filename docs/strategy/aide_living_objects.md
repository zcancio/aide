# AIde — Living Objects

**Author:** Zach Cancio
**Date:** 2025-02-13
**Status:** Product thesis — the foundation everything else builds on

---

## The Idea

What if things could talk and mutate themselves?

Your poker league has a page. The page knows it's a poker league. It knows who's playing next week, who's on snacks, what the rotation looks like. When you tell it "Mike's out, Dave's subbing," it reshapes itself. Not because you edited a cell in a spreadsheet or dragged a card on a board. Because the thing heard you and updated.

The page is alive. It maintains its own coherence. It has memory. It has continuity. It doesn't care how you reach it — browser, phone, screenshot, voice. It just listens, and stays current.

An aide is not a tool you use to manage something. An aide *is* the thing you're running, in living form.

---

## What a Living Object Is

A living object has five properties:

**1. It has state.** The poker league page knows the roster, the schedule, the rotation, the budget. This is not a document someone maintains. It's the current truth, held by the object itself.

**2. It has voice.** The object can speak — but only in state reflections. "Next game: Thursday. Dave's on snacks." It never says "I updated the roster for you!" It speaks the way a scoreboard speaks: by showing how things stand.

**3. It mutates through conversation.** You don't edit the object. You talk to it. "Mike's out this week." The object hears, understands, and reshapes. The conversation is the interface. There is no other interface.

**4. It's reachable from anywhere.** If the object is alive, constraining where you can talk to it is artificial. You should be able to reach it from a browser, a phone, a screenshot, a group chat, a voice memo. The channel is irrelevant. The object is listening from wherever you find it.

**5. It's shareable as a single artifact.** The object has a URL. Anyone with the link sees the current state. The URL never changes. The state always reflects the latest truth. Sharing the object is sharing the thing itself, not a copy of it.

**6. It carries its own blueprint.** The published page embeds everything needed to reconstruct the aide: its identity, its current state, its conversation history, its voice rules, and a prompt that any LLM can use to become its brain. The aide is fully self-contained. Download the HTML file and you have the entire living object — not a snapshot, but the DNA to bring it back to life with any model, on any infrastructure.

```html
<!-- Published aide: toaide.com/s/poker-league -->
<html>
  <!-- The visible page: roster, schedule, standings -->
  ...
  
  <script type="application/aide+json">
  {
    "identity": "Poker league. 8 players, biweekly Thursday.",
    "state": { /* current structured state */ },
    "voice": "No first person. State reflections only.",
    "prompt": "You are maintaining a living page for a poker 
               league. Here is the current state. When the user 
               tells you something changed, update the state and 
               regenerate the page..."
  }
  </script>
</html>
```

This means: no lock-in. If AIde disappears, every published page still carries everything needed to continue. Paste the prompt into Claude, ChatGPT, Gemini, a local model — the aide comes back to life. Different brain, same body, same identity. Forking a page forks the entire living object — state, voice, blueprint. AIde the product is a convenient way to create and maintain these objects. But the objects are yours.

---

## What a Living Object Is Not

A chess board is an aide. Each piece is not.

A calendar is an aide. Each event is not.

A renovation is an aide. The contractor's phone number is not.

The test is: **does this thing need to talk?** Does it need to maintain itself through conversation? Does it need its own voice, its own URL, its own history? If yes, it's an aide. If no, it's state within an aide.

| Aide (the thing you're running) | State (what it knows) |
|---|---|
| Poker league | Players, schedule, rotation, scores |
| Chess board | Pieces, positions, move history |
| Calendar | Events, dates, reminders |
| Renovation | Budget, contractors, timeline, decisions |
| Trip | Itinerary, packing list, budget splits |

Nobody says "I'm running this pawn." They say "I'm running this game."

An aide is the smallest thing that needs its own voice and its own URL. Everything inside it is just what it knows. This prevents the system from fracturing into a million micro-aides that are really just database rows pretending to be alive. The living object idea only works at the right level — the level where someone would say "I'm running this."

### Aides can reference aides

A collection of aides is also a thing someone runs. If you have five aides — poker league, renovation, trip, household, standup — you might create a sixth that watches the others. "I'm running my life. Here are the things I'm tracking."

```
User: What needs my attention?

Aide: Poker league — no host confirmed for Feb 27.
      Renovation — contractor invoice overdue.
      Trip — 2 people haven't confirmed flights.
      
      Household and standup are current.
```

This isn't a system feature or an automatic hierarchy. It's just another aide, created the same way as any other — by describing what you're running. The nesting emerges from use, not from architecture.

The constraint: an aide-of-aides is still infrastructure, not a personal assistant. It doesn't presume to organize your life. You tell it what to watch, and it watches.

---

## Starting in the Middle

Living objects don't need a creation ceremony. You don't sit down and say "I'm going to create a document about my grocery situation." You text "we need milk and that pasta Sarah likes" and the aide figures out it's maintaining a grocery list.

There's no blank page. No template picker. No "What are you running?" as a required first prompt. You just start talking and the aide catches up.

```
Signal group chat with your partner:

Zach: hey we need milk, eggs, and that sourdough 
      from Whole Foods

Aide: Grocery list started.
      — Milk
      — Eggs  
      — Sourdough (Whole Foods)
      
      toaide.com/s/k8m2n updated.

Partner: Add the stuff for tacos tuesday

Aide: For taco Tuesday:
      — Ground beef or chicken?
      — Tortillas, cheese, salsa, lettuce added.
      
      Page updated.

Partner: chicken. oh and we're out of olive oil

Aide: — Chicken (for tacos)
      — Olive oil
      
      Page updated.
```

The aide didn't need to be told "this is a grocery list." It heard the conversation and understood. It asked one clarifying question (chicken or beef) because it needed to. It maintained the page from the first message.

This is fundamentally different from every other tool. Notion needs you to create a page, pick a template, define properties. Google Docs needs you to open a blank document. Even ChatGPT starts with a blank conversation that you have to frame. A living object just listens and forms.

**What "starting in the middle" requires:**

- **Intent detection without framing.** The first message doesn't say "create a grocery list." The aide infers it from "we need milk and eggs."
- **Incremental state building.** The shape of the page emerges over time. First message: a simple list. By the tenth message: categories, store preferences, recurring items. The aide reshapes as it learns more.
- **Asking the right questions at the right time.** "Ground beef or chicken?" is good. "What template would you like to use for your grocery management system?" is death.
- **Multi-user context.** In a Signal group, the aide knows who's talking. "I got the milk" from your partner means check it off.

The aide doesn't need structured import to get started. Conversation *is* the import. If someone has an existing list in Apple Notes, they screenshot it and drop it in — the image ear handles it. For complex aides, structured import (CSV, another aide's blueprint) can come later. But for most things, you just start talking and the aide catches up.

---

## Why This Changes the Product

The current framing is: AIde is a conversational web page editor. You talk to it, and it makes pages.

The reframing is: AIde creates living objects. You describe what you're running, and a living thing comes into existence. It knows its purpose, it maintains itself, and it's reachable from anywhere.

This isn't just language. It changes what you build.

**Editor-first thinking** leads to: build a split-pane web interface, add a dashboard, optimize the creation flow, then maybe add mobile and integrations later.

**Living-object thinking** leads to: make the object alive and responsive, then give it as many ears as possible. The "editor" is just one ear. The web chat, WhatsApp, Telegram, a screenshot, a share sheet — these are all just ways to reach a thing that's already alive.

The investment priority flips. Instead of spending months on a polished web editor and then bolting on channels, you spend the effort on the core (the living object) and the output (the published page), then add input channels incrementally. Each new channel is just another ear.

---

## Architecture of a Living Object

```
EARS (input — any channel)       BRAIN (server)             BODY (web)
                                                         
├─ Web chat                      ├─ Channel router          ├─ Published HTML page
├─ Voice (speech-to-text)        ├─ L2: Intent compiler     ├─ Shareable URL
├─ Signal                        │   (Haiku → primitives)   ├─ Embedded blueprint
├─ Screenshot/image drop         ├─ L3: Schema + macros     ├─ Embedded state + events
├─ Telegram (future)             │   (Sonnet → MacroSpecs)  ├─ "Made with AIde" footer
├─ WhatsApp (future)             ├─ Reducer + renderer      └─ toaide.com/s/{slug}
├─ Share sheet (future)          ├─ Event log
└─ (anything that sends text,    └─ User/aide DB
    images, or audio to an API)
```

**Ears** receive input from any source and normalize it: user identity, aide identity, message content (text, image, audio, or any combination). Each ear is a thin adapter. Adding a new ear never changes the brain or the body.

**Brain** is the FastAPI backend. It receives normalized messages and compiles them into structured state transitions through a tiered AI: a fast, cheap model (Haiku-class) handles ~90% of messages by pattern-matching against a set of 25 declarative primitives. A slower model (Sonnet-class) handles novel requests by synthesizing new capabilities — including the initial schema when an aide first comes alive. These capabilities persist as macros, so the system grows its own vocabulary over time: the slow model teaches the fast model, and the aide gets cheaper to run the longer it lives. The full architecture is in `aide_architecture.md`.

**Body** is the published page. A single HTML file served via Cloudflare R2/CDN. It contains the rendered page, the structured state, the event history, and the aide's blueprint — a prompt that any LLM can use to become the aide's brain. The body is the *output* of the object's life — the accumulated result of every conversation it's had. It's also the thing that makes the aide yours, not ours: download the file and you have everything needed to bring the aide back to life anywhere.

---

## The Ears, Prioritized

Not all ears are equal. Prioritized by what's buildable now vs. what comes later:

### v1: Three ears

**Web chat** — the existing interface, simplified. No split-pane editor. Just a chat with the aide, plus a link to view the published page. This is the universal fallback. Everyone has a browser.
├─ Voice (speech-to-text)        ├─ L2: Intent compiler     ├─ Shareable URL

**Image input** — the human integration layer. Screenshots of conversations, photos of receipts, pictures of whiteboards and scoreboards. The user brings context from their life; the aide extracts what matters and reshapes the page. This is how people already move information between apps — they screenshot. AIde just needs to be great at reading what they show it.

**Signal** — the first channel ear. AIde gets a dedicated Signal phone number. Users text it directly or add it to a group chat. Built on signal-cli-rest-api, an open-source Signal client that exposes a REST API. Runs as a container alongside the FastAPI backend on Railway. Proven path — people run production bots on it, Home Assistant uses it. Cost: one phone number (~$1/month) and a lightweight container process.

Signal is the dogfood ear. It's the messaging app we use daily with the people we coordinate with. Building it first means we live with it, find the rough edges, and prove the channel-ear model works before adding more channels. It also validates group chat collaboration — add the aide's number to a Signal group and everyone in the group can update the page.

Image input remains the universal bridge for everything Signal doesn't cover. Screenshot a WhatsApp chat, photograph a scoreboard, snap a handwritten note — the aide reads it regardless of where it came from.

### v2: More ears

**Telegram bot** — zero approval, zero cost, rich bot API. Good for developer/early-adopter audience. The aide gets a Telegram handle; you DM it or add it to a group.

**WhatsApp** — the growth ear. 2B+ users. This is where most of AIde's target users already coordinate. Requires Business API approval or the reverse-engineered path (Baileys) which carries platform risk but is faster to ship.

**Share sheet (mobile)** — on iOS and Android, share a piece of text or an image from any app directly to AIde. "Share → AIde → page updates." No app switching. Two taps.

### v3: Even more ears

**Voice memo** — speak what changed. The aide transcribes and processes.

**Slack / Discord** — for community and enterprise contexts.

**Email forwarding** — forward an email thread to your aide's address. It extracts what matters.

**Webhooks / API** — programmatic updates for power users and integrations.

Each new ear is a small adapter. The cost of adding one is measured in days, not months, because the brain doesn't change.

---

## The v1 Experience

The v1 is a living object with four ears (web chat, images, voice, Signal) and a body (published page).

### Creation

```
1. Land on toaide.com. "What are you running?"
2. Type: "I run a poker league. 8 guys, every other Thursday."
3. The aide comes alive. Page forms: roster, schedule, rotation.
4. URL is live. Share it.
```

No account required for the first 10 turns. Email to save. Managed AI by default.

### Creation (from chat export)

The stronger creation path — for someone who already has a group chat full of history:

```
1. Export your Signal or WhatsApp group chat (both support .txt export)
2. Drop the file into AIde
3. "This is my poker league. Build a page from this."
4. The aide reads months of messy coordination — names, 
   dates, scores, who owes what, the last argument about 
   snack rotation — and distills it into a coherent page
5. Add the aide to the group chat going forward
```

The export *is* the description. The user doesn't have to remember or retype anything. Three months of scattered group chat becomes a living page in one step.

### Maintenance (text)

```
User: Mike's out this week. Dave's subbing.

Aide: Next game: Thursday Feb 27.
      Dave replaces Mike. Dave's on snacks.
      
      Page updated.
```

### Maintenance (screenshot)

```
User: [drops screenshot of WhatsApp group chat where 
       three people discussed game changes]

Aide: From the conversation:
      — Mike is out Feb 27
      — Dave is subbing
      — Game moved to 7:30 PM (was 7:00)
      
      Page updated with all three changes.
```

### Maintenance (photo)

```
User: [photo of handwritten score sheet from game night]

Aide: Scores recorded for Feb 13:
      Zach: 340, Dave: 280, Chris: 310, James: 195
      Season standings updated.
      
      Page updated.
```

The aide doesn't care if you typed it, exported it, screenshotted it, or photographed it. It hears, it understands, it reshapes.

---

## What This Means for the Existing Plans

### Core identity (aide_prd.md)

The product definition strengthens. Everything in the PRD — voice system, state reflections, reflect → afford → act, the design litmus test — is more true in this framing, not less. The aide being a living object is the *reason* it speaks in state reflections. Living things don't say "I updated the roster for you." They just *are* their current state.

What changes: the framing shifts from "conversational web page editor" to "living objects, reachable from anywhere." The §3 User Flow should reflect this. The architecture (§5) should describe the ears/brain/body model. The "What This Is Not" section gains a line: "This is not a page editor. There is no editor. There is conversation, and there is the living page."

### Launch plan (aide_launch_plan.md)

The 6-week timeline simplifies in some ways, intensifies in others:

**Simpler:** The web interface is a full-page preview of the aide with a floating chat overlay at the bottom — you're looking at the page and talking to it. The chat expands on demand and collapses after use. Same layout on desktop and mobile. That's less frontend work than a traditional editor and reinforces the living object metaphor: you're talking to the thing, not to a tool that manages the thing.

**Intensifies:** Image understanding needs to be excellent from day one. If screenshots are the bridge to every other app, the aide needs to read them reliably — messy group chat screenshots, receipts at angles, handwritten notes. This is mostly about prompt engineering and model selection (vision calls to Sonnet when images are present, Haiku for text-only).

**Unchanged:** Auth (magic links), rate limiting, managed API routing, Stripe, published page serving, landing page — all the same.

| Current phase | Living objects equivalent |
|---|---|
| Phase 0: Foundation | Same — domain, rebrand, auth |
| Phase 1: Multi-aide + editor UI | Multi-aide + simplified chat UI + image input + voice input + Signal ear (signal-cli-rest-api) |
| Phase 2: Rate limiting | Same |
| Phase 3: Payments | Same |
| Phase 4: Landing page | Same, but framed around "things that stay alive" |

### Channel integrations (future)

Each new ear is a future milestone, not a launch requirement:

- **M2 or M3:** Telegram bot (days of work, proves multi-ear model)
- **M3 or M4:** WhatsApp (requires API approval, larger integration)
- **M4+:** Share sheet, voice, email, webhooks

The key architectural decision for v1: build the brain to accept normalized messages from *any* source, even if web chat is the only ear at launch. This means the channel adapter pattern is in place from day one, and adding Telegram later is just writing a new adapter — not refactoring the core.

---

## Group Chats: The Collaborative Unlock

Signal group chats are collaborative aides from v1:

```
[Poker League Group Chat — aide is a member]

Mike: Hey I can't make it Thursday

Aide: Mike is out for Feb 27.
      7 players confirmed.
      Need a sub?

Dave: I'll sub in

Aide: Dave is in for Feb 27. 8 players confirmed.
      Dave — you're on snacks (Mike's rotation slot).
      
      Page updated.
```

No auth model. No permissions UI. No invite flow. The group chat *is* the collaboration layer. The messaging platform handles presence, membership, and notifications. The aide just listens and reshapes.

This solves §9.2 (Collaborative Pages) from the PRD without building multi-user infrastructure. The group chat is the multi-user infrastructure. It already exists.

For channels that don't have a direct ear yet (WhatsApp, iMessage, Slack), the fallback still works: screenshot the conversation and drop it into AIde via web chat. The living object still hears — just through the human.

---

## The Human as Integration Point

There's a second model that coexists with channel ears: the human *is* the router. You don't need AIde in every group chat if you're willing to be the bridge. You read the conversation, you screenshot the relevant parts, you drop them into AIde. You attend the game, you photograph the score sheet, you show it to the aide.

This model has a deep advantage: it works with *everything*, not just the channels AIde has ears for. There's no API for a handwritten note on a fridge. There's no webhook for a conversation you had in a parking lot. But you can take a photo and show it to the aide.

The human-as-router model and the channel-ears model aren't competing. They're complementary:

- **v1:** Signal is the direct ear. For everything else, the human is the router — screenshots, photos, typed summaries.
- **v2+:** More channel ears (Telegram, WhatsApp) reduce friction for more sources. Human remains the router for everything else.
- **Eventually:** The aide has so many ears that the human rarely needs to route manually. But the option is always there.

The image input capability is what makes the human-as-router model viable. Without it, being the bridge means retyping everything. With it, the bridge is: screenshot → drop → done.

---

## The Sci-Fi Reference

The closest analog isn't a tool or an interface. It's the idea that objects can be alive.

A PADD from Star Trek — a focused surface for one thing, shareable by handing it to someone. But a PADD doesn't maintain itself.

The ship's log — a living record updated through voice. But the log is passive; it doesn't reshape itself.

The real reference is closer to animism: the ancient idea that objects have awareness. The poker league page *knows* it's a poker league. The renovation timeline *knows* the contractor pushed to March. You talk to the object, and the object responds by becoming its new state.

There isn't a clean sci-fi reference because science fiction wants AI to be general. A narrow intelligence that just maintains one thing — that's boring to write about. But it's exactly what people need.

---

## What Doesn't Change

These hold true regardless of how many ears the object has:

- **The page is the body.** A living, shareable URL. Standalone HTML. Anyone with the link sees the current state. Every page carries its own blueprint — the embedded prompt, state, and voice rules that any LLM can use to bring the aide back to life. The objects are yours, not ours.
- **The voice system.** No first person, no encouragement, state reflections only. The object speaks by showing how things stand.
- **Reflect → Afford → Act.** The interaction model holds in every channel. Affordances adapt to the medium (buttons in Telegram, quick replies in WhatsApp, UI elements in web chat) but the pattern is the same: observe, surface, wait.
- **Managed-first, BYOK available.** Everyone starts on managed AI. BYOK is available in settings for those who want it.
- **The monetization model.** Free (50 turns/week, footer) → Pro ($10/month, unlimited, no footer) → BYOK (free, bring your key).
- **The infrastructure.** Railway, Neon, R2, Cloudflare. The brain doesn't care which ear is talking.
- **The design litmus test.** Does this feel like infrastructure? Or does it feel like software trying to impress? If it performs, remove it. If it stabilizes, keep it.

---

## Summary

AIde creates living objects. You describe what you're running, and a thing comes alive. It maintains its own state through conversation. It's reachable from anywhere you can send text, images, or voice. It's shareable as a single URL.

v1 gives the object four ears: web chat, image input, voice input, and Signal. The published page is its body. The human is the router between their life and the object — and Signal is the first channel where the aide listens directly.

v2+ gives it more ears: Telegram, WhatsApp, share sheet. Each ear reduces friction. The human routes less. The object hears more.

The object is always alive. You just keep giving it more ways to listen.
