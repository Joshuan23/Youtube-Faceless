"""Text-to-speech voiceover generation.

Priority: ElevenLabs → edge-tts (free, natural) → OpenAI TTS → gTTS
edge-tts uses Microsoft Edge voices — natural quality, completely free, no key needed.
"""

import os
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EDGE_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")   # change in .env


class VoiceoverGenerator:
    def __init__(self):
        self.provider = self._detect_provider()
        logger.info("TTS provider: %s", self.provider)

    def _detect_provider(self) -> str:
        if os.getenv("ELEVENLABS_API_KEY"):
            return "elevenlabs"
        try:
            import edge_tts  # noqa: F401
            return "edge_tts"
        except ImportError:
            pass
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        return "gtts"

    def generate(self, text: str, output_path: str) -> str:
        """Generate an MP3 voiceover file. Returns output_path."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if self.provider == "elevenlabs":
            return self._elevenlabs(text, output_path)
        if self.provider == "edge_tts":
            return self._edge_tts(text, output_path)
        if self.provider == "openai":
            return self._openai(text, output_path)
        return self._gtts(text, output_path)

    # ── edge-tts (free, natural voices) ─────────────────────────────────

    def _edge_tts(self, text: str, output_path: str) -> str:
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, EDGE_VOICE)
            await communicate.save(output_path)

        asyncio.run(_run())
        logger.info("edge-tts audio saved: %s", output_path)
        return output_path

    # ── ElevenLabs ───────────────────────────────────────────────────────

    def _elevenlabs(self, text: str, output_path: str) -> str:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import VoiceSettings

        api_key = os.getenv("ELEVENLABS_API_KEY")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

        client = ElevenLabs(api_key=api_key)
        audio = client.generate(
            text=text,
            voice=voice_id,
            model="eleven_turbo_v2_5",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.8,
                style=0.2,
                use_speaker_boost=True,
            ),
        )
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        logger.info("ElevenLabs audio saved: %s", output_path)
        return output_path

    # ── OpenAI TTS ───────────────────────────────────────────────────────

    def _openai(self, text: str, output_path: str) -> str:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice="onyx",
            input=text,
            response_format="mp3",
        )
        with open(output_path, "wb") as f:
            f.write(response.content)
        logger.info("OpenAI TTS audio saved: %s", output_path)
        return output_path

    # ── gTTS (free fallback) ──────────────────────────────────────────────

    def _gtts(self, text: str, output_path: str) -> str:
        from gtts import gTTS

        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(output_path)
        logger.info("gTTS audio saved: %s", output_path)
        return output_path


def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split long scripts into chunks safe for ElevenLabs (5k char limit)."""
    words = text.split()
    chunks, current = [], []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars:
            chunks.append(" ".join(current))
            current, current_len = [word], len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


async def _edge_tts_parallel(chunks: list[str], paths: list[str], voice: str):
    """Generate all chunks simultaneously with edge-tts."""
    import edge_tts

    async def _one(text, path):
        await edge_tts.Communicate(text, voice).save(path)

    await asyncio.gather(*[_one(c, p) for c, p in zip(chunks, paths)])


def generate_chunked(text: str, output_dir: str, filename_base: str) -> str:
    """Generate voiceover in chunks and concatenate into one MP3. Returns final path."""
    gen = VoiceoverGenerator()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = chunk_text(text)
    chunk_paths = [str(output_dir / f"{filename_base}_part{i}.mp3") for i in range(len(chunks))]

    if gen.provider == "edge_tts" and len(chunks) > 1:
        # All chunks in parallel — cuts multi-chunk audio time by ~60%
        asyncio.run(_edge_tts_parallel(chunks, chunk_paths, EDGE_VOICE))
    else:
        for chunk, path in zip(chunks, chunk_paths):
            gen.generate(chunk, path)

    if len(chunk_paths) == 1:
        final = str(output_dir / f"{filename_base}.mp3")
        Path(chunk_paths[0]).rename(final)
        return final

    from pydub import AudioSegment
    combined = AudioSegment.empty()
    for path in chunk_paths:
        combined += AudioSegment.from_mp3(path)

    final_path = str(output_dir / f"{filename_base}.mp3")
    combined.export(final_path, format="mp3")
    for p in chunk_paths:
        Path(p).unlink(missing_ok=True)
    logger.info("Combined audio: %s (%d chunks)", final_path, len(chunks))
    return final_path
