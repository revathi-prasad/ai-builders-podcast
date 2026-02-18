"""Tests for the audio synthesizer."""

import os
import pytest
from unittest.mock import patch, MagicMock
from src.agents.synthesizer import (
    VibeVoiceSynthesizer, AudioSynthesisAgent,
    DialogueSegment, VoiceProfile, SynthesisResult
)


class TestVibeVoiceSynthesizer:
    def test_vibevoice_not_available(self):
        """VibeVoice should report as unavailable when not installed."""
        synth = VibeVoiceSynthesizer()
        assert not synth.vibevoice_available

    def test_elevenlabs_detection(self):
        """Should detect ElevenLabs API key."""
        synth = VibeVoiceSynthesizer()
        assert not synth._check_elevenlabs()  # No key set by default

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_key"}):
            assert synth._check_elevenlabs()

    def test_default_voices(self):
        """Should have default voice profiles."""
        synth = VibeVoiceSynthesizer()
        assert "Host" in synth.default_voices
        assert "Expert" in synth.default_voices

    def test_empty_segments_raises(self, tmp_dir):
        synth = VibeVoiceSynthesizer(output_dir=tmp_dir)
        with pytest.raises(ValueError, match="No segments"):
            synth.synthesize([])

    def test_no_tts_backend_raises(self, tmp_dir):
        """Should raise if no TTS backend is available."""
        synth = VibeVoiceSynthesizer(output_dir=tmp_dir, fallback_to_gtts=False)
        synth.vibevoice_available = False

        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                segments = [DialogueSegment(speaker="Host", text="Hello")]
                with pytest.raises(RuntimeError, match="No TTS backend"):
                    synth.synthesize(segments)

    def test_list_voices(self):
        synth = VibeVoiceSynthesizer()
        voices = synth.list_available_voices()
        assert "Host" in voices
        assert "Expert" in voices


class TestAudioSynthesisAgent:
    def test_process_empty_segments(self):
        agent = AudioSynthesisAgent()
        result = agent.process({"script_segments": []})
        assert result.get("error")
        assert result.get("audio_path") is None

    def test_process_with_mock_synthesizer(self):
        """Agent should delegate to synthesizer."""
        mock_synth = MagicMock()
        mock_synth.synthesize.return_value = SynthesisResult(
            audio_path="/tmp/test.wav",
            duration_seconds=120.0,
            segments_synthesized=3,
            model_used="mock",
            voice_profiles=["Host", "Expert"],
            metadata={"format": "wav"}
        )

        agent = AudioSynthesisAgent(synthesizer=mock_synth)
        result = agent.process({
            "script_segments": [
                {"speaker": "Host", "text": "Hello!"},
                {"speaker": "Expert", "text": "Great topic!"},
            ]
        })

        assert result["audio_path"] == "/tmp/test.wav"
        assert result["audio_duration"] == 120.0
        mock_synth.synthesize.assert_called_once()


class TestDialogueSegment:
    def test_defaults(self):
        seg = DialogueSegment(speaker="Host", text="Hello")
        assert seg.emotion is None
        assert seg.pace == 1.0

    def test_custom_values(self):
        seg = DialogueSegment(speaker="Expert", text="Wow!", emotion="excited", pace=1.5)
        assert seg.emotion == "excited"
        assert seg.pace == 1.5
