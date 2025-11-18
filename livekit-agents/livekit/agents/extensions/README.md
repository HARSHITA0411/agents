# Filler-Aware Interruption Handler for LiveKit Agents
## Assignment Submission — Harshita

## 1. What Changed (Overview of New Modules, Params, and Logic Added)
### New Module Added

```
livekit/agents/extensions/filler_interrupt_handler.py
```

This file implements a custom interruption handler that enhances the LiveKit voice agent by preventing accidental interruptions caused by:

- Filler words (uh, umm, hmm)

- Background mouth noises

- Low-confidence STT segments

The handler introduces:

- handle_transcript_segment() → Processes ASR + interruption logic

- on_tts_start() → Marks when the agent begins speaking

- on_tts_end() → Marks when the agent stops speaking

- InterruptConfig() → Threshold configs (confidence, filler lists, etc.)

### Modifications to Existing File

```
livekit/agents/voice/agent_session.py
```

Integrated the custom handler into the agent pipeline.

- **Added Import:**
``` python
from livekit.agents.extensions.filler_interrupt_handler import (
    FillerAwareInterruptHandler,
    InterruptConfig,
)
```

- **Instantiated Handler:**

Inside __init__():
``` python
self.interrupt_handler = FillerAwareInterruptHandler(InterruptConfig())
```
- **Hooked into Agent TTS State:**

Inside _update_agent_state():

``` python
self.interrupt_handler.on_tts_start()
...
self.interrupt_handler.on_tts_end()
```

- **Replaced Default STT Handling:**

Overrode _user_input_transcribed() so all transcripts pass through the new logic:

``` python
self.interrupt_handler.handle_transcript_segment(
    text=text,
    confidence=confidence,
    is_final=is_final,
    stop_agent_tts=stop_tts,
    forward_to_nlu=forward_to_nlu,
)
```

Added helper for passing final text to LiveKit:

``` python
_user_input_transcribed_raw()
```
---

## 2. What Works (Verified Features)
1. **Intelligent interruption logic**

- Agent only interrupts on meaningful human speech

- Agent does NOT interrupt for:

    - uh

    - um

    - hmm

    - breath sounds

    - partial phonemes

    - low confidence noise

2. **Full compatibility with LiveKit session flow**

- User speech correctly forwarded to LLM

- Chat history preserved

- No interference with VAD, STT, or TTS engines

3. **Toggle-safe design**

- TTS state is tracked properly

- Silent → Listening transitions work

- Filler detection works even for partial STT output

---

## 3. Known Issues / Edge Cases

| Issue                     | Description                                               | Impact                                    |
|--------------------------|-----------------------------------------------------------|--------------------------------------------|
| Partial filler detection | Some STT engines output phonemes like `"uh-"`             | Might pass as non-filler                   |
| Accented fillers         | Non-English filler words not included                     | Requires language-specific extension       |
| Fast interrupt phrases   | User saying “uh stop…” very quickly                       | First filler may delay interruption slightly |
| Confidence scoring varies | Some STT providers omit confidence scores                 | Fallback value may misclassify rare cases |

These issues do not break the agent, but may affect accuracy in rare scenarios.

---

## 4. Steps to Test the Implementation
### Step 1 — Launch a test agent

Example:
``` bash
python examples/voice_agents/basic_agent.py
```

Or with console mode:

``` bash
python myagent.py console
```

### Step 2 — Speak while the agent is talking

| You Say        | Expected Behavior        |
|----------------|---------------------------|
| "uh..."        | ❌ No interruption        |
| "umm..."       | ❌ No interruption        |
| "hmm..."       | ❌ No interruption        |
| breath noise   | ❌ No interruption        |
| "hello?"       | ✔ Agent stops speaking   |
| "wait wait"    | ✔ Agent interrupts       |
| "stop"         | ✔ Instant interruption   |

---

### Step 3 — Speak while the agent is silent

| You Say | Expected Behavior         |
|---------|----------------------------|
| "uh..." |  Sent to NLU normally     |
| Real speech  |  Processed normally       |

### Step 4 — Check logs (optional)

Enable logging to confirm TTS start/end signals.

---

## 5. Environment Details

### Python Version:

Tested on Python 3.10+

Dependencies:
Installed via:

``` bash
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]"
```

### Required Configurations:
Environment variables depending on the chosen STT/LLM/TTS:

``` makefile
DEEPGRAM_API_KEY=
OPENAI_API_KEY=
ELEVEN_API_KEY=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```

No additional dependencies needed beyond LiveKit Agents and provider SDKs.

---

## Summary

This implementation adds a robust, state-aware interruption system that improves conversational quality by eliminating false-positive interruptions. The changes are clean, modular, and integrate naturally into the existing LiveKit architecture.

---

## Author

Harshita
NSUT – SalesCode AI Step 2 Assignment

Branch:
https://github.com/HARSHITA0411/agents/tree/feature/livekit-interrupt-handler-harshita
