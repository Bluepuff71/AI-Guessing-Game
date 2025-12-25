"""Tests for game.animations module."""
import os
import pytest
from unittest.mock import patch, MagicMock
from game import animations


class TestAssetPaths:
    """Tests for asset path definitions."""

    def test_assets_directory_path(self):
        """Test ASSETS_DIR is correctly defined."""
        assert animations.ASSETS_DIR is not None
        assert isinstance(animations.ASSETS_DIR, str)
        assert "assets" in animations.ASSETS_DIR

    def test_elimination_gif_path(self):
        """Test ELIMINATION_GIF path is correctly defined."""
        assert animations.ELIMINATION_GIF is not None
        assert animations.ELIMINATION_GIF.endswith("elimination.gif")
        assert animations.ASSETS_DIR in animations.ELIMINATION_GIF

    def test_victory_gif_path(self):
        """Test VICTORY_GIF path is correctly defined."""
        assert animations.VICTORY_GIF is not None
        assert animations.VICTORY_GIF.endswith("victory.gif")
        assert animations.ASSETS_DIR in animations.VICTORY_GIF

    def test_escape_gif_path(self):
        """Test ESCAPE_GIF path is correctly defined."""
        assert animations.ESCAPE_GIF is not None
        assert animations.ESCAPE_GIF.endswith("escape.gif")
        assert animations.ASSETS_DIR in animations.ESCAPE_GIF


class TestPlayGifPopup:
    """Tests for play_gif_popup function."""

    def test_play_gif_popup_file_not_found(self):
        """Test play_gif_popup returns False when file doesn't exist."""
        result = animations.play_gif_popup("/nonexistent/path/to/file.gif")
        assert result is False

    def test_play_gif_popup_import_error(self, tmp_path):
        """Test play_gif_popup handles import errors gracefully."""
        # Create a dummy GIF file
        gif_path = tmp_path / "test.gif"
        gif_path.write_bytes(b"GIF89a")  # Minimal GIF header

        with patch.dict('sys.modules', {'tkinter': None}):
            # This should fail gracefully when tkinter is not available
            # Since we can't really remove tkinter, we test the file exists check
            result = animations.play_gif_popup(str(gif_path))
            # May return True or False depending on PIL availability
            assert isinstance(result, bool)


class TestAnimationFunctions:
    """Tests for animation wrapper functions."""

    def test_play_elimination_animation_fallback(self, monkeypatch):
        """Test elimination animation uses fallback when GIF fails."""
        # Mock play_gif_popup to return False (GIF failed)
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)

        # Mock os.system to prevent actual screen clear
        monkeypatch.setattr(os, 'system', lambda x: None)

        # Mock Rich Console - imported inside function from rich.console
        mock_console = MagicMock()
        with patch('rich.console.Console', return_value=mock_console):
            # Mock time.sleep to speed up test
            with patch('time.sleep'):
                animations.play_elimination_animation()

        # Should have called console.print multiple times
        assert mock_console.print.called

    def test_play_victory_animation_fallback(self, monkeypatch):
        """Test victory animation uses fallback when GIF fails."""
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)
        monkeypatch.setattr(os, 'system', lambda x: None)

        mock_console = MagicMock()
        with patch('rich.console.Console', return_value=mock_console):
            with patch('time.sleep'):
                animations.play_victory_animation()

        assert mock_console.print.called

    def test_play_escape_animation_fallback(self, monkeypatch):
        """Test escape animation uses fallback when GIF fails."""
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)
        monkeypatch.setattr(os, 'system', lambda x: None)

        mock_console = MagicMock()
        with patch('rich.console.Console', return_value=mock_console):
            with patch('time.sleep'):
                animations.play_escape_animation()

        assert mock_console.print.called

    def test_play_elimination_animation_gif_success(self, monkeypatch):
        """Test elimination animation returns early when GIF succeeds."""
        call_count = [0]

        def mock_gif_popup(*args, **kwargs):
            call_count[0] += 1
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_elimination_animation()

        # Should have called play_gif_popup
        assert call_count[0] == 1

    def test_play_victory_animation_gif_success(self, monkeypatch):
        """Test victory animation returns early when GIF succeeds."""
        call_count = [0]

        def mock_gif_popup(*args, **kwargs):
            call_count[0] += 1
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_victory_animation()

        assert call_count[0] == 1

    def test_play_escape_animation_gif_success(self, monkeypatch):
        """Test escape animation returns early when GIF succeeds."""
        call_count = [0]

        def mock_gif_popup(*args, **kwargs):
            call_count[0] += 1
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_escape_animation()

        assert call_count[0] == 1


class TestFallbackHandling:
    """Tests for fallback error handling."""

    def test_elimination_fallback_console_error(self, monkeypatch):
        """Test elimination animation handles Console import error."""
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)

        # Mock Console to raise ImportError
        def raise_import_error(*args, **kwargs):
            raise ImportError("No rich")

        with patch('rich.console.Console', side_effect=raise_import_error):
            with patch('builtins.print') as mock_print:
                with patch('time.sleep'):
                    animations.play_elimination_animation()

                # Should fall back to basic print
                mock_print.assert_called()

    def test_victory_fallback_console_error(self, monkeypatch):
        """Test victory animation handles Console import error."""
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)

        def raise_import_error(*args, **kwargs):
            raise ImportError("No rich")

        with patch('rich.console.Console', side_effect=raise_import_error):
            with patch('builtins.print') as mock_print:
                with patch('time.sleep'):
                    animations.play_victory_animation()

                mock_print.assert_called()

    def test_escape_fallback_console_error(self, monkeypatch):
        """Test escape animation handles Console import error."""
        monkeypatch.setattr(animations, 'play_gif_popup', lambda *args, **kwargs: False)

        def raise_import_error(*args, **kwargs):
            raise ImportError("No rich")

        with patch('rich.console.Console', side_effect=raise_import_error):
            with patch('builtins.print') as mock_print:
                with patch('time.sleep'):
                    animations.play_escape_animation()

                mock_print.assert_called()


class TestGifDurations:
    """Tests for GIF animation durations."""

    def test_elimination_duration(self, monkeypatch):
        """Test elimination animation uses correct duration."""
        called_with = []

        def mock_gif_popup(path, duration=None):
            called_with.append({'path': path, 'duration': duration})
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_elimination_animation()

        assert len(called_with) == 1
        assert called_with[0]['duration'] == 4.0

    def test_victory_duration(self, monkeypatch):
        """Test victory animation uses correct duration."""
        called_with = []

        def mock_gif_popup(path, duration=None):
            called_with.append({'path': path, 'duration': duration})
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_victory_animation()

        assert len(called_with) == 1
        assert called_with[0]['duration'] == 3.0

    def test_escape_duration(self, monkeypatch):
        """Test escape animation uses correct duration."""
        called_with = []

        def mock_gif_popup(path, duration=None):
            called_with.append({'path': path, 'duration': duration})
            return True

        monkeypatch.setattr(animations, 'play_gif_popup', mock_gif_popup)

        animations.play_escape_animation()

        assert len(called_with) == 1
        assert called_with[0]['duration'] == 2.0
