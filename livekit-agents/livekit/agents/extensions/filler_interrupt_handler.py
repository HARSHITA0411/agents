import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Set

logger = logging.getLogger(__name__)


def _parse_csv_env(name: str, default: Iterable[str]) -> Set[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return set(w.lower() for w in default)
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


@dataclass
class InterruptConfig:
    """
    Runtime configuration for filler-aware interruption handling.
    """
    ignored_words: Set[str] = field(default_factory=lambda: _parse_csv_env(
        "LIVEKIT_IGNORED_WORDS", ["uh", "umm", "hmm", "haan"]
    ))
    interrupt_keywords: Set[str] = field(default_factory=lambda: _parse_csv_env(
        "LIVEKIT_INTERRUPT_KEYWORDS", ["stop", "wait", "hold on", "no", "cancel"]
    ))
    min_confidence: float = float(os.getenv("LIVEKIT_MIN_ASR_CONFIDENCE", "0.55"))


class FillerAwareInterruptHandler:
    """
    Extension-layer controller that decides whether to ignore or act
    on ASR segments based on filler words, confidence, and agent TTS state.

    - Does NOT modify LiveKit's VAD.
    - Uses ASR results (transcription events).
    """

    def __init__(self, config: InterruptConfig | None = None):
        self.config = config or InterruptConfig()
        self.agent_speaking: bool = False

    # ---- Hooks for TTS state -------------------------------------------------

    def on_tts_start(self) -> None:
        """Call when agent TTS starts speaking."""
        self.agent_speaking = True
        logger.debug("TTS started -> agent_speaking=True")

    def on_tts_end(self) -> None:
        """Call when agent TTS fully stops."""
        self.agent_speaking = False
        logger.debug("TTS ended -> agent_speaking=False")

    # ---- Text processing helpers --------------------------------------------

    def _normalize_text(self, text: str) -> str:
        return text.strip().lower()

    def _tokens(self, text: str) -> list[str]:
        # Alphanumeric tokens only
        return re.findall(r"\w+", text.lower())

    def _is_filler_only(self, text: str) -> bool:
        tokens = self._tokens(text)
        if not tokens:
            return False
        ignored = self.config.ignored_words
        return all(tok in ignored for tok in tokens)

    def _contains_interrupt_keyword(self, text: str) -> bool:
        norm = self._normalize_text(text)
        for kw in self.config.interrupt_keywords:
            if kw in norm:
                return True
        return False

    # ---- Main decision entrypoint -------------------------------------------

    def handle_transcript_segment(
        self,
        text: str,
        confidence: float,
        is_final: bool,
        stop_agent_tts: Callable[[], None],
        forward_to_nlu: Callable[[str], None],
    ) -> None:
        """
        Decide what to do with a new ASR segment.

        - stop_agent_tts: callback that stops TTS immediately.
        - forward_to_nlu: callback that feeds user text into the dialogue logic.
        """

        if not text.strip():
            return

        norm = self._normalize_text(text)
        logger.debug(
            "ASR segment received: text=%r, conf=%.3f, is_final=%s, speaking=%s",
            norm, confidence, is_final, self.agent_speaking
        )

        # Ignore very low confidence segments when agent is speaking
        if self.agent_speaking and confidence < self.config.min_confidence:
            logger.info(
                "Ignored low-confidence background segment: text=%r, conf=%.3f",
                norm, confidence
            )
            return

        # If agent is not speaking, everything is "valid speech" by requirement
        if not self.agent_speaking:
            logger.info("Agent quiet -> forwarding speech: %r", norm)
            forward_to_nlu(norm)
            return

        # Agent is speaking at this point
        is_filler = self._is_filler_only(norm)
        has_interrupt_kw = self._contains_interrupt_keyword(norm)

        if is_filler and not has_interrupt_kw:
            # Pure filler while TTS is talking -> ignore
            logger.info("Ignored filler-only interruption while speaking: %r", norm)
            return

        # "umm okay stop" or similar: treat as real interruption
        if has_interrupt_kw:
            logger.info("Valid interruption (keyword) detected: %r", norm)
            stop_agent_tts()
            forward_to_nlu(norm)
            return

        # Otherwise: non-filler, non-keyword speech while TTS active
        logger.info("User interruption detected: %r", norm)
        stop_agent_tts()
        forward_to_nlu(norm)

    # ---- (Optional) Dynamic updates at runtime -------------------------------

    def update_ignored_words(self, new_words: Iterable[str]) -> None:
        """
        Bonus: dynamically update ignored filler list at runtime.
        """
        self.config.ignored_words = {w.lower().strip() for w in new_words if w.strip()}
        logger.info("Updated ignored_words to: %s", self.config.ignored_words)
