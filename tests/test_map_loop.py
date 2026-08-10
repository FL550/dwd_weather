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
    fallback = loop._find_fallback(target, available, now)
    assert fallback == img_sample

    # Current or future timestamps should not get a fallback image
    assert loop._find_fallback(now, available, now) is None
    assert loop._find_fallback(now + timedelta(minutes=5), available, now) is None

    # Empty available should return None
    assert loop._find_fallback(target, {}, now) is None


def test_future_image_loop_skips_now_frame_when_no_image_is_available():
    """Missing current radar images should not be replaced by a stale fallback frame."""
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
        steps_future=0,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    available = {now - timedelta(minutes=5): Image.new("RGB", (10, 10))}

    assert loop._find_fallback(now, available, now) is None


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


def test_future_image_loop_keeps_timestamps_aligned_with_available_images():
    """Missing frames should remove both the timestamp and the image slot together."""
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
        steps_future=0,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    past_img = Image.new("RGB", (10, 10))

    def _mock_fetch(date):
        if date == now:
            return None
        if date == now - timedelta(minutes=5):
            return past_img
        return None

    with patch.object(loop, "_get_image_safe", side_effect=_mock_fetch):
        with patch(
            "custom_components.dwd_weather.map_loop.get_time_last_5_min",
            return_value=now,
        ):
            loop.update()

    assert len(loop._images) == len(loop._all_times)
    assert loop._all_times == [now - timedelta(minutes=5)]


def test_future_image_loop_keeps_future_timestamps_when_images_are_identical():
    """Distinct future timestamps must remain even if image bytes are identical."""
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
        steps_future=0,
        hours_future=2,
        speed=0.5,
        speed_future=2.0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    identical_img = Image.new("RGB", (10, 10))

    with patch.object(loop, "_get_image_safe", return_value=identical_img):
        with patch(
            "custom_components.dwd_weather.map_loop.get_time_last_5_min",
            return_value=now,
        ):
            loop.update()

    expected_times = [
        now - timedelta(minutes=5),
        now,
    ]
    first_model = datetime(2026, 8, 9, 13, 0, 0, tzinfo=timezone.utc)
    second_model = datetime(2026, 8, 9, 14, 0, 0, tzinfo=timezone.utc)
    expected_times.extend([first_model] * 4)
    expected_times.extend([second_model] * 4)

    assert loop._all_times == expected_times
    assert len(loop._images) == len(expected_times)


def test_future_image_loop_drops_duplicate_now_boundary_frame_when_future_enabled():
    """Drop now when it is identical to now-5 and future playback is active."""
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
        steps_future=1,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    identical_observed = Image.new("RGB", (10, 10), color=(10, 10, 10))
    future_img = Image.new("RGB", (10, 10), color=(30, 30, 30))

    def _mock_fetch(date):
        if date == now - timedelta(minutes=5):
            return identical_observed
        if date == now:
            return identical_observed
        if date == now + timedelta(minutes=5):
            return future_img
        return None

    with patch.object(loop, "_get_image_safe", side_effect=_mock_fetch):
        with patch(
            "custom_components.dwd_weather.map_loop.get_time_last_5_min",
            return_value=now,
        ):
            loop.update()

    assert loop._all_times == [now - timedelta(minutes=5), now + timedelta(minutes=5)]
    assert len(loop._images) == 2
