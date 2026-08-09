"""Tests for the FutureImageLoop weather map loop generator."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from PIL import Image

from custom_components.dwd_weather.map_loop import FutureImageLoop


def test_future_image_loop_initialization():
    """Test initializing FutureImageLoop does not trigger synchronous fetches."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        image_width=520,
        image_height=580,
        steps_past=6,
        steps_future=12,
        hours_future=3,
        dark_mode=False,
    )

    assert loop._minx == 9.0
    assert loop._miny == 47.0
    assert loop._steps_past == 6
    assert loop._steps_future == 12
    assert loop._hours_future == 3
    assert loop.get_images() == []


def test_future_image_loop_find_fallback():
    """Test nearest-neighbor fallback logic for missing timestamps."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        image_width=520,
        image_height=580,
        steps_past=6,
        steps_future=12,
        hours_future=3,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    img_sample = Image.new("RGB", (10, 10))

    available = {
        now - timedelta(minutes=10): img_sample,
    }

    # Timestamp with available image should find nearest
    target = now - timedelta(minutes=5)
    fallback = loop._find_fallback(target, available)
    assert fallback == img_sample

    # Empty available should return None
    assert loop._find_fallback(target, {}) is None


def test_future_image_loop_update():
    """Test update method builds loop images and uses cache."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        image_width=520,
        image_height=580,
        steps_past=2,
        steps_future=2,
        hours_future=1,
    )

    mock_img = Image.new("RGB", (100, 100))

    with patch.object(loop, "_get_image_safe", return_value=mock_img) as mock_fetch:
        loop.update()
        images = loop.get_images()
        assert len(images) > 0
        assert mock_fetch.called
