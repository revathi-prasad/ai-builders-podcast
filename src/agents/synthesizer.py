"""
Audio Synthesis Agent using VibeVoice TTS

This agent converts podcast scripts to audio using Microsoft's VibeVoice,
a multi-speaker TTS model that supports:
- Up to 4 distinct speakers per session
- Voice cloning from 10-60s audio samples
- Long-form generation (up to 90 minutes)

Models:
- VibeVoice-1.5B: Fast (RTF ~0.2), good quality (MOS 4.3)
- VibeVoice-7B: High quality (MOS 4.5), slower (RTF ~0.8)

References:
- https://github.com/microsoft/VibeVoice
- https://github.com/vibevoice-community/VibeVoice
"""

import os
import json
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfile:
    """Configuration for a speaker's voice"""
    name: str
    reference_audio: Optional[str] = None  # Path to 10-60s audio sample for cloning
    style: str = "conversational"  # conversational, formal, energetic, calm
    language: str = "en"


@dataclass
class DialogueSegment:
    """A single segment of dialogue to synthesize"""
    speaker: str
    text: str
    emotion: Optional[str] = None  # happy, sad, excited, neutral
    pace: float = 1.0  # 0.5 to 2.0


@dataclass
class SynthesisResult:
    """Result of audio synthesis"""
    audio_path: str
    duration_seconds: float
    segments_synthesized: int
    model_used: str
    voice_profiles: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class VibeVoiceSynthesizer:
    """
    Audio synthesis using VibeVoice TTS

    Supports multi-speaker podcast generation with optional voice cloning.
    Falls back to gTTS if VibeVoice is not available.
    """

    def __init__(
        self,
        model_size: Literal["1.5B", "7B"] = "1.5B",
        output_dir: str = "outputs/audio",
        use_gpu: bool = True,
        fallback_to_gtts: bool = True
    ):
        self.model_size = model_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.fallback_to_gtts = fallback_to_gtts

        # Check VibeVoice availability
        self.vibevoice_available = self._check_vibevoice()

        # Default voice profiles for podcast hosts
        self.default_voices = {
            "Host": VoiceProfile(name="Host", style="conversational"),
            "Expert": VoiceProfile(name="Expert", style="formal"),
            "Alice": VoiceProfile(name="Alice", style="energetic"),
            "Bob": VoiceProfile(name="Bob", style="calm"),
        }

    def _check_vibevoice(self) -> bool:
        """Check if VibeVoice is installed and available"""
        try:
            import vibevoice
            return True
        except ImportError:
            logger.warning("VibeVoice not installed. Install with: pip install vibevoice")
            return False

    def _check_gtts(self) -> bool:
        """Check if gTTS fallback is available"""
        try:
            from gtts import gTTS
            return True
        except ImportError:
            return False

    def _check_elevenlabs(self) -> bool:
        """Check if ElevenLabs API is available"""
        return bool(os.environ.get("ELEVENLABS_API_KEY"))

    def synthesize(
        self,
        segments: List[DialogueSegment],
        voice_profiles: Optional[Dict[str, VoiceProfile]] = None,
        output_filename: Optional[str] = None
    ) -> SynthesisResult:
        """
        Synthesize audio from dialogue segments

        Fallback chain: VibeVoice → ElevenLabs → gTTS → error

        Args:
            segments: List of DialogueSegment with speaker and text
            voice_profiles: Optional custom voice profiles per speaker
            output_filename: Optional output filename (auto-generated if not provided)

        Returns:
            SynthesisResult with path to generated audio
        """
        if not segments:
            raise ValueError("No segments provided for synthesis")

        # Merge with default voices
        voices = {**self.default_voices}
        if voice_profiles:
            voices.update(voice_profiles)

        # Generate output filename
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"podcast_{timestamp}.wav"

        output_path = self.output_dir / output_filename

        # Fallback chain: VibeVoice → ElevenLabs → gTTS → error
        if self.vibevoice_available:
            return self._synthesize_vibevoice(segments, voices, output_path)
        elif self._check_elevenlabs():
            logger.info("Using ElevenLabs TTS (VibeVoice not available)")
            return self._synthesize_elevenlabs(segments, voices, output_path)
        elif self.fallback_to_gtts and self._check_gtts():
            logger.info("Using gTTS fallback (VibeVoice and ElevenLabs not available)")
            return self._synthesize_gtts(segments, voices, output_path)
        else:
            raise RuntimeError(
                "No TTS backend available. Options:\n"
                "  pip install vibevoice      # High-quality multi-speaker\n"
                "  ELEVENLABS_API_KEY=...     # ElevenLabs cloud TTS\n"
                "  pip install gtts           # Basic fallback"
            )

    def _synthesize_vibevoice(
        self,
        segments: List[DialogueSegment],
        voices: Dict[str, VoiceProfile],
        output_path: Path
    ) -> SynthesisResult:
        """Synthesize using VibeVoice multi-speaker TTS"""
        try:
            from vibevoice import VibeVoice, Speaker

            # Initialize model
            model_name = f"microsoft/VibeVoice-{self.model_size}"
            model = VibeVoice.from_pretrained(model_name, device="cuda" if self.use_gpu else "cpu")

            # Create speakers
            speakers = {}
            for name, profile in voices.items():
                if profile.reference_audio and os.path.exists(profile.reference_audio):
                    # Voice cloning mode
                    speakers[name] = Speaker.from_audio(
                        profile.reference_audio,
                        name=name
                    )
                else:
                    # Use built-in voice
                    speakers[name] = Speaker(name=name, style=profile.style)

            # Build dialogue for synthesis
            dialogue = []
            for seg in segments:
                speaker = speakers.get(seg.speaker, speakers.get("Host"))
                dialogue.append({
                    "speaker": speaker,
                    "text": seg.text,
                    "emotion": seg.emotion,
                    "rate": seg.pace
                })

            # Synthesize
            audio = model.synthesize_dialogue(dialogue)

            # Save audio
            audio.save(str(output_path))

            return SynthesisResult(
                audio_path=str(output_path),
                duration_seconds=audio.duration,
                segments_synthesized=len(segments),
                model_used=f"VibeVoice-{self.model_size}",
                voice_profiles=list(set(s.speaker for s in segments)),
                metadata={
                    "sample_rate": audio.sample_rate,
                    "channels": 1,
                    "format": "wav"
                }
            )

        except Exception as e:
            logger.error(f"VibeVoice synthesis failed: {e}")
            if self.fallback_to_gtts:
                logger.info("Falling back to gTTS")
                return self._synthesize_gtts(segments, voices, output_path)
            raise

    def _synthesize_elevenlabs(
        self,
        segments: List[DialogueSegment],
        voices: Dict[str, VoiceProfile],
        output_path: Path
    ) -> SynthesisResult:
        """Synthesize using ElevenLabs API (multi-voice cloud TTS)."""
        import httpx
        from pydub import AudioSegment

        api_key = os.environ["ELEVENLABS_API_KEY"]

        # Map speaker names to ElevenLabs voice IDs
        # These are default ElevenLabs voices; users can override via voice_profiles
        default_voice_map = {
            "Host": "21m00Tcm4TlvDq8ikWAM",       # Rachel
            "Expert": "ErXwobaYiN019PkySvjV",      # Antoni
            "Priya": "21m00Tcm4TlvDq8ikWAM",       # Rachel (female)
            "Arjun": "ErXwobaYiN019PkySvjV",       # Antoni (male)
            "Alice": "EXAVITQu4vr4xnSDxMaL",       # Bella
            "Bob": "VR6AewLTigWG4xSOukaG",         # Arnold
        }

        audio_chunks = []
        pause_ms = 500  # 0.5s pause between segments

        try:
            with httpx.Client(timeout=30.0) as client:
                for seg in segments:
                    voice_id = default_voice_map.get(seg.speaker, default_voice_map["Host"])

                    response = client.post(
                        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                        headers={
                            "xi-api-key": api_key,
                            "Content-Type": "application/json",
                            "Accept": "audio/mpeg"
                        },
                        json={
                            "text": seg.text,
                            "model_id": "eleven_monolingual_v1",
                            "voice_settings": {
                                "stability": 0.5,
                                "similarity_boost": 0.75
                            }
                        }
                    )
                    response.raise_for_status()

                    # Save chunk to temp file and load as AudioSegment
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(response.content)
                        tmp_path = tmp.name

                    chunk = AudioSegment.from_mp3(tmp_path)
                    audio_chunks.append(chunk)
                    os.unlink(tmp_path)

                    logger.debug(f"  [ElevenLabs] Synthesized {seg.speaker}: {len(seg.text)} chars")

            # Concatenate with pauses
            silence = AudioSegment.silent(duration=pause_ms)
            combined = AudioSegment.empty()
            for i, chunk in enumerate(audio_chunks):
                if i > 0:
                    combined += silence
                combined += chunk

            # Export as WAV
            combined.export(str(output_path), format="wav")
            duration = len(combined) / 1000.0

            return SynthesisResult(
                audio_path=str(output_path),
                duration_seconds=duration,
                segments_synthesized=len(segments),
                model_used="ElevenLabs-v1",
                voice_profiles=list(set(s.speaker for s in segments)),
                metadata={
                    "sample_rate": combined.frame_rate,
                    "channels": combined.channels,
                    "format": "wav",
                    "pause_between_segments_ms": pause_ms
                }
            )

        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            if self.fallback_to_gtts and self._check_gtts():
                logger.info("Falling back to gTTS")
                return self._synthesize_gtts(segments, voices, output_path)
            raise

    def _synthesize_gtts(
        self,
        segments: List[DialogueSegment],
        voices: Dict[str, VoiceProfile],
        output_path: Path
    ) -> SynthesisResult:
        """Fallback synthesis using Google TTS (single voice, no cloning)"""
        from gtts import gTTS
        from pydub import AudioSegment

        # Combine all text with speaker labels
        combined_segments = []

        for seg in segments:
            # Add speaker announcement for multi-speaker simulation
            combined_segments.append(f"{seg.speaker} says:")
            combined_segments.append(seg.text)

        full_text = " ".join(combined_segments)

        # Determine language from first voice profile
        lang = "en"
        for v in voices.values():
            if v.language:
                lang = v.language[:2]  # Take first 2 chars (en, hi, ta, etc.)
                break

        # Generate speech
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tts = gTTS(text=full_text, lang=lang, slow=False)
            tts.save(tmp.name)

            # Convert to WAV
            audio = AudioSegment.from_mp3(tmp.name)
            audio.export(str(output_path), format="wav")

            # Clean up temp file
            os.unlink(tmp.name)

        # Get duration
        audio = AudioSegment.from_wav(str(output_path))
        duration = len(audio) / 1000.0

        return SynthesisResult(
            audio_path=str(output_path),
            duration_seconds=duration,
            segments_synthesized=len(segments),
            model_used="gTTS-fallback",
            voice_profiles=list(set(s.speaker for s in segments)),
            metadata={
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "format": "wav",
                "note": "Single voice fallback - VibeVoice not available"
            }
        )

    def clone_voice(
        self,
        reference_audio: str,
        speaker_name: str,
        min_duration: float = 10.0,
        max_duration: float = 60.0
    ) -> VoiceProfile:
        """
        Create a voice profile from a reference audio sample

        Args:
            reference_audio: Path to audio file (10-60 seconds recommended)
            speaker_name: Name for this voice
            min_duration: Minimum audio duration required
            max_duration: Maximum audio duration to use

        Returns:
            VoiceProfile configured for voice cloning
        """
        if not os.path.exists(reference_audio):
            raise FileNotFoundError(f"Reference audio not found: {reference_audio}")

        # Validate audio duration
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(reference_audio)
            duration = len(audio) / 1000.0

            if duration < min_duration:
                raise ValueError(
                    f"Reference audio too short ({duration:.1f}s). "
                    f"Need at least {min_duration}s for voice cloning."
                )

            if duration > max_duration:
                logger.warning(
                    f"Reference audio ({duration:.1f}s) exceeds {max_duration}s. "
                    "Only first 60s will be used for cloning."
                )
        except ImportError:
            logger.warning("pydub not available, skipping duration validation")

        return VoiceProfile(
            name=speaker_name,
            reference_audio=reference_audio,
            style="cloned"
        )

    def list_available_voices(self) -> List[str]:
        """List available built-in voices"""
        voices = list(self.default_voices.keys())

        if self.vibevoice_available:
            try:
                from vibevoice import list_voices
                voices.extend(list_voices())
            except:
                pass

        return list(set(voices))


class AudioSynthesisAgent:
    """
    LangGraph-compatible agent for audio synthesis

    Takes script segments from the Generator agent and produces audio.
    """

    def __init__(self, synthesizer: Optional[VibeVoiceSynthesizer] = None):
        self.synthesizer = synthesizer or VibeVoiceSynthesizer()

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process state and synthesize audio

        Expected state keys:
            - script_segments: List of dialogue segments
            - voice_config: Optional voice configuration
            - output_dir: Optional output directory

        Returns updated state with:
            - audio_path: Path to generated audio
            - audio_duration: Duration in seconds
            - synthesis_metadata: Additional synthesis info
        """
        segments_data = state.get("script_segments", [])
        voice_config = state.get("voice_config", {})

        if not segments_data:
            return {
                **state,
                "error": "No script segments provided for synthesis",
                "audio_path": None
            }

        # Convert to DialogueSegment objects
        segments = []
        for seg in segments_data:
            segments.append(DialogueSegment(
                speaker=seg.get("speaker", "Host"),
                text=seg.get("text", ""),
                emotion=seg.get("emotion"),
                pace=seg.get("pace", 1.0)
            ))

        # Build voice profiles
        voice_profiles = {}
        for name, config in voice_config.items():
            voice_profiles[name] = VoiceProfile(
                name=name,
                reference_audio=config.get("reference_audio"),
                style=config.get("style", "conversational"),
                language=config.get("language", "en")
            )

        try:
            result = self.synthesizer.synthesize(
                segments=segments,
                voice_profiles=voice_profiles if voice_profiles else None
            )

            return {
                **state,
                "audio_path": result.audio_path,
                "audio_duration": result.duration_seconds,
                "synthesis_metadata": {
                    "model": result.model_used,
                    "voices": result.voice_profiles,
                    "segments_count": result.segments_synthesized,
                    **result.metadata
                }
            }

        except Exception as e:
            logger.error(f"Audio synthesis failed: {e}")
            return {
                **state,
                "error": f"Audio synthesis failed: {str(e)}",
                "audio_path": None
            }


# Convenience function for direct use
def synthesize_podcast(
    script_segments: List[Dict[str, str]],
    output_path: Optional[str] = None,
    model_size: str = "1.5B"
) -> str:
    """
    Quick function to synthesize a podcast from script segments

    Args:
        script_segments: List of {"speaker": str, "text": str} dicts
        output_path: Optional output path
        model_size: "1.5B" (fast) or "7B" (quality)

    Returns:
        Path to generated audio file
    """
    synthesizer = VibeVoiceSynthesizer(model_size=model_size)

    segments = [
        DialogueSegment(speaker=s["speaker"], text=s["text"])
        for s in script_segments
    ]

    result = synthesizer.synthesize(
        segments=segments,
        output_filename=output_path
    )

    return result.audio_path
