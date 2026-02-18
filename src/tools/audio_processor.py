"""
Audio Processor using faster-whisper

This module transcribes audio files using faster-whisper, which is:
- 4x faster than OpenAI's Whisper
- MIT licensed (no restrictions)
- Supports CPU and GPU inference
- Includes word-level timestamps
- Supports speaker diarization (with additional setup)

Why faster-whisper over alternatives?
- OpenAI Whisper: Slower, more GPU memory needed
- WhisperX: Better diarization, but more complex setup
- AssemblyAI/Deepgram: Paid APIs
- faster-whisper: Best balance for local inference
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio"""
    text: str
    start: float  # Start time in seconds
    end: float    # End time in seconds
    speaker: Optional[str] = None
    confidence: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Result from audio transcription"""
    text: str                                    # Full transcript
    segments: List[TranscriptSegment]            # Timed segments
    language: str                                # Detected language
    duration_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_hash: str = ""
    transcription_timestamp: datetime = field(default_factory=datetime.now)


class AudioProcessor:
    """
    Process audio files and generate transcripts.

    Usage:
        processor = AudioProcessor(model_size="base")
        result = processor.transcribe("audio.mp3")
        print(result.text)
        for seg in result.segments:
            print(f"[{seg.start:.1f}s] {seg.text}")
    """

    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4'}
    MODEL_SIZES = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3']

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",  # "auto", "cpu", or "cuda"
        compute_type: str = "auto",  # "auto", "int8", "float16", "float32"
        language: Optional[str] = None,  # None = auto-detect
        enable_word_timestamps: bool = True
    ):
        """
        Initialize the audio processor.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            device: Computation device (auto, cpu, cuda)
            compute_type: Computation precision (affects speed vs accuracy)
            language: Force language (None = auto-detect)
            enable_word_timestamps: Include word-level timing
        """
        if model_size not in self.MODEL_SIZES:
            raise ValueError(f"Invalid model size. Choose from: {self.MODEL_SIZES}")

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.enable_word_timestamps = enable_word_timestamps
        self._model = None

    def _ensure_model(self):
        """Lazy load the Whisper model"""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise ImportError(
                    "faster-whisper is not installed. "
                    "Install with: pip install faster-whisper"
                )

            # Determine device and compute type
            device = self.device
            compute_type = self.compute_type

            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

            if compute_type == "auto":
                compute_type = "float16" if device == "cuda" else "int8"

            print(f"[AudioProcessor] Loading {self.model_size} model on {device}...")
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type
            )
            print(f"[AudioProcessor] Model loaded successfully")

    def transcribe(
        self,
        file_path: str,
        prompt: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            file_path: Path to the audio file
            prompt: Optional prompt to guide transcription (e.g., technical terms)

        Returns:
            TranscriptionResult with full transcript and timed segments
        """
        self._ensure_model()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported audio format: {ext}. "
                f"Supported formats: {self.SUPPORTED_FORMATS}"
            )

        # Calculate file hash
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # Transcribe
        try:
            segments_generator, info = self._model.transcribe(
                file_path,
                language=self.language,
                word_timestamps=self.enable_word_timestamps,
                initial_prompt=prompt,
                vad_filter=True,  # Voice Activity Detection for cleaner output
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            # Process segments
            segments = []
            full_text_parts = []

            for segment in segments_generator:
                words = []
                if self.enable_word_timestamps and segment.words:
                    words = [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability
                        }
                        for w in segment.words
                    ]

                transcript_segment = TranscriptSegment(
                    text=segment.text.strip(),
                    start=segment.start,
                    end=segment.end,
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0,
                    words=words
                )
                segments.append(transcript_segment)
                full_text_parts.append(segment.text.strip())

            # Get duration from last segment
            duration = segments[-1].end if segments else 0.0

            return TranscriptionResult(
                text=' '.join(full_text_parts),
                segments=segments,
                language=info.language,
                duration_seconds=duration,
                metadata={
                    "model_size": self.model_size,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                    "language_probability": info.language_probability
                },
                source_hash=file_hash
            )

        except Exception as e:
            raise RuntimeError(f"Failed to transcribe audio: {e}")

    def transcribe_with_diarization(
        self,
        file_path: str,
        num_speakers: Optional[int] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio with speaker diarization.

        Note: This requires additional setup (pyannote.audio)
        and a Hugging Face token for the diarization model.

        Args:
            file_path: Path to the audio file
            num_speakers: Expected number of speakers (None = auto-detect)

        Returns:
            TranscriptionResult with speaker labels
        """
        # First get basic transcription
        result = self.transcribe(file_path)

        # Diarization would require pyannote.audio
        # This is a placeholder for the full implementation
        try:
            from pyannote.audio import Pipeline
            import torch
        except ImportError:
            print(
                "[Warning] Speaker diarization requires pyannote.audio. "
                "Install with: pip install pyannote.audio"
            )
            return result

        # Full diarization implementation would go here
        # For now, return transcription without speaker labels
        return result

    def get_audio_duration(self, file_path: str) -> float:
        """Get the duration of an audio file in seconds"""
        try:
            import soundfile as sf
            info = sf.info(file_path)
            return info.duration
        except ImportError:
            # Fallback using ffmpeg-python
            try:
                import ffmpeg
                probe = ffmpeg.probe(file_path)
                return float(probe['format']['duration'])
            except Exception:
                return 0.0


def extract_audio_from_video(
    video_path: str,
    output_path: Optional[str] = None,
    audio_format: str = "mp3"
) -> str:
    """
    Extract audio track from a video file.

    Args:
        video_path: Path to the video file
        output_path: Path for output audio (auto-generated if None)
        audio_format: Output audio format (mp3, wav, m4a)

    Returns:
        Path to the extracted audio file
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError(
            "ffmpeg-python is not installed. "
            "Install with: pip install ffmpeg-python"
        )

    if output_path is None:
        base_name = os.path.splitext(video_path)[0]
        output_path = f"{base_name}.{audio_format}"

    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_path, acodec='libmp3lame' if audio_format == 'mp3' else None)
            .overwrite_output()
            .run(quiet=True)
        )
        return output_path
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to extract audio: {e}")
