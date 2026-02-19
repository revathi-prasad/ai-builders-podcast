"""Tests for the CLI entry point."""

import sys
import pytest
from unittest.mock import patch, MagicMock


class TestCLI:
    def test_import(self):
        """CLI module should be importable."""
        from src.cli import main
        assert callable(main)

    def test_main_module_importable(self):
        """__main__.py should be importable."""
        import importlib
        spec = importlib.util.find_spec("src.__main__")
        assert spec is not None

    def test_help_flag(self):
        """--help should print usage and exit."""
        from src.cli import main
        with patch.object(sys, 'argv', ['prog', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_missing_topic_fails(self):
        """Missing --topic should fail."""
        from src.cli import main
        with patch.object(sys, 'argv', ['prog']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_args_parsing(self):
        """Test argument parsing with valid inputs."""
        import argparse
        from src.cli import main

        # We can't easily test main() end-to-end without mocking the pipeline,
        # so verify argparse works by checking it doesn't error on valid args
        with patch.object(sys, 'argv', [
            'prog', '--topic', 'Test Topic',
            '--language', 'english', '--duration', '5',
            '--format', 'conversation', '--audience', 'beginner'
        ]):
            with patch('src.agents.graph.generate_podcast_sync') as mock_gen:
                mock_gen.return_value = {
                    "processing_status": "completed",
                    "final_script": "test",
                    "audio_file_path": None,
                    "overall_quality_score": 0.8,
                    "script_segments": [],
                    "trace_id": "test-123",
                }
                # Should run without error
                main()

                # Verify it was called with the right topic
                call_args = mock_gen.call_args
                assert call_args[1]["user_request"] == "Test Topic"
                assert call_args[1]["target_language"] == "english"
                assert call_args[1]["target_duration_minutes"] == 5
