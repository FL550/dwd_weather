"""Tests for the FutureImageLoop weather map loop generator."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from PIL import Image
import pytest

from custom_components.dwd_weather.map_loop import (
    _FRAME_NOT_PUBLISHED,
    _WMS_TIMEOUT,
    FrameNotPublished,
    FutureImageLoop,
)
from simple_dwd_weatherforecast.dwdmap import WeatherBackgroundMapType, WeatherMapType


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

    # Far-away timestamps eventually fall back to last available image
    far_past = now - timedelta(hours=3)
    assert loop._find_fallback(far_past, available, now) == img_sample


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


def test_future_image_loop_skips_refetch_for_complete_unchanged_slot():
    """A complete loop should be reused until the 5-minute slot changes."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        steps_past=1,
        steps_future=1,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    img = Image.new("RGB", (10, 10))

    with patch(
        "custom_components.dwd_weather.map_loop.get_time_last_5_min",
        return_value=now,
    ):
        with patch.object(loop, "_get_image_safe", return_value=img) as mock_fetch:
            loop.update()
            loop.update()

    assert mock_fetch.call_count == 2
    assert loop._last_complete is True


def test_future_image_loop_retries_incomplete_unchanged_slot():
    """An incomplete loop should retry within the same 5-minute slot."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        steps_past=1,
        steps_future=1,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    now_img = Image.new("RGB", (10, 10))
    future_img = Image.new("RGB", (10, 10), color=(4, 4, 4))

    def _first_fetch(date):
        if date == now:
            return now_img
        return None

    with patch(
        "custom_components.dwd_weather.map_loop.get_time_last_5_min",
        return_value=now,
    ):
        with patch.object(loop, "_get_image_safe", side_effect=_first_fetch):
            loop.update()
        with patch.object(loop, "_get_image_safe", return_value=future_img) as mock_retry:
            loop.update()

    assert mock_retry.call_count == 2
    assert loop._last_complete is True


def test_future_image_loop_skips_unpublished_frame_retries_within_slot():
    """Unpublished edge frames should not prevent same-slot loop reuse."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        steps_past=1,
        steps_future=1,
        hours_future=0,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    now_img = Image.new("RGB", (10, 10))

    def _fetch(date):
        if date == now:
            return now_img
        return _FRAME_NOT_PUBLISHED

    with patch(
        "custom_components.dwd_weather.map_loop.get_time_last_5_min",
        return_value=now,
    ):
        with patch.object(loop, "_get_image_safe", side_effect=_fetch):
            loop.update()
        with patch.object(loop, "_get_image_safe") as mock_retry:
            loop.update()

    assert mock_retry.call_count == 0
    assert loop._last_complete is True


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


def test_future_image_loop_images_equal_handles_exceptions():
    """_images_equal should return False when image bytes access fails."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
    )

    first = Image.new("RGB", (10, 10), color=(1, 2, 3))
    second = MagicMock()
    second.mode = "RGB"
    second.size = (10, 10)
    second.tobytes.side_effect = RuntimeError("broken image")

    assert loop._images_equal(first, second) is False


def test_future_image_loop_get_image_safe_returns_none_on_error():
    """_get_image_safe should swallow fetch errors and return None."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
    )

    with patch.object(loop, "_get_image", side_effect=ConnectionError("boom")):
        assert loop._get_image_safe(datetime.now(timezone.utc)) is None


def test_future_image_loop_get_image_builds_model_layer_url_and_dark_mode_bg():
    """_get_image should request model layer and dark mode background when configured."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=[WeatherMapType.NIEDERSCHLAGSRADAR],
        background_types=[
            WeatherBackgroundMapType.SATELLIT,
            WeatherBackgroundMapType.LAENDER,
        ],
        dark_mode=True,
    )

    date = datetime(2026, 8, 9, 13, 0, 0, tzinfo=timezone.utc)
    loop._model_times = {date}

    image = Image.new("RGB", (4, 4), color=(20, 20, 20))
    content = MagicMock()
    content.status_code = 200
    content.headers = {"content-type": "image/png"}

    from io import BytesIO

    raw = BytesIO()
    image.save(raw, format="PNG")
    content.content = raw.getvalue()

    with patch(
        "custom_components.dwd_weather.map_loop.requests.get", return_value=content
    ) as mock_get:
        with patch(
            "custom_components.dwd_weather.map_loop.draw_marker",
            side_effect=lambda img, *_: img,
        ):
            result = loop._get_image(date)

    assert result.size == (4, 4)
    request_url = mock_get.call_args[0][0]
    assert mock_get.call_args.kwargs["timeout"] == _WMS_TIMEOUT
    assert (
        "layers=dwd:bluemarble,dwd:Icon-eu_reg00625_fd_sl_TOTPREC01H,dwd:Laender"
        in request_url
    )
    assert "styles=,niederschlagsradar," in request_url
    assert "bgcolor=0x1C1C1C" in request_url


@pytest.mark.parametrize(
    "status_code,content_type,error_type",
    [
        (500, "image/png", ConnectionError),
        (200, "text/xml", TypeError),
    ],
)
def test_future_image_loop_get_image_raises_for_invalid_response(
    status_code,
    content_type,
    error_type,
):
    """_get_image should fail fast for non-200 or non-image responses."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=[WeatherMapType.NIEDERSCHLAGSRADAR],
        background_types=[],
    )

    date = datetime(2026, 8, 9, 13, 0, 0, tzinfo=timezone.utc)
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"content-type": content_type}
    response.content = b"ignored"

    with patch(
        "custom_components.dwd_weather.map_loop.requests.get", return_value=response
    ):
        with pytest.raises(error_type):
            loop._get_image(date)


def test_future_image_loop_get_image_raises_frame_not_published_for_service_exception():
    """ServiceException XML should be treated as an unpublished frame."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=[WeatherMapType.NIEDERSCHLAGSRADAR],
        background_types=[],
    )

    date = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/xml"}
    response.content = b"<ServiceExceptionReport><ServiceException/></ServiceExceptionReport>"

    with patch(
        "custom_components.dwd_weather.map_loop.requests.get", return_value=response
    ):
        with pytest.raises(FrameNotPublished):
            loop._get_image(date)


def test_future_image_loop_get_image_raises_runtime_error_when_image_parsing_fails():
    """_get_image should raise RuntimeError when PNG payload cannot be parsed."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=[WeatherMapType.NIEDERSCHLAGSRADAR],
        background_types=[],
    )

    date = datetime(2026, 8, 9, 13, 0, 0, tzinfo=timezone.utc)
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "image/png"}
    response.content = b"not-a-valid-png"

    with patch(
        "custom_components.dwd_weather.map_loop.requests.get", return_value=response
    ):
        with patch(
            "custom_components.dwd_weather.map_loop.Image.open",
            side_effect=OSError("bad image"),
        ):
            with pytest.raises(RuntimeError):
                loop._get_image(date)


def test_future_image_loop_reuses_non_expired_model_cache():
    """Valid model cache entries should be reused without refetching model frames."""
    loop = FutureImageLoop(
        minx=9.0,
        miny=47.0,
        maxx=15.0,
        maxy=55.0,
        map_types=["niederschlagsradar"],
        background_types=[],
        steps_past=1,
        steps_future=0,
        hours_future=1,
    )

    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    model_time = datetime(2026, 8, 9, 13, 0, 0, tzinfo=timezone.utc)
    model_cached = Image.new("RGB", (10, 10), color=(7, 7, 7))
    now_img = Image.new("RGB", (10, 10), color=(8, 8, 8))

    loop._model_cache_time = now
    loop._model_cache = {model_time: model_cached}

    with patch(
        "custom_components.dwd_weather.map_loop.get_time_last_5_min",
        return_value=now,
    ):
        with patch.object(loop, "_get_image_safe", return_value=now_img) as mock_fetch:
            loop.update()

    assert mock_fetch.call_count == 1
    assert mock_fetch.call_args[0][0] == now
    assert loop._all_times == [now, model_time, model_time, model_time, model_time]
    assert len(loop._images) == len(loop._all_times)
