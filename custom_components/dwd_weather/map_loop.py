from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from io import BytesIO
import logging
from typing import Iterable

from PIL import Image, ImageFile
import requests
from simple_dwd_weatherforecast.dwdmap import (
    ImageBoundaries,
    Marker,
    WeatherBackgroundMapType,
    WeatherMapType,
    draw_marker,
    get_time_last_5_min,
)

try:
    from .const import CONF_MAP_DEFAULT_WMS_STYLE
except (ImportError, ModuleNotFoundError):
    try:
        from const import CONF_MAP_DEFAULT_WMS_STYLE
    except (ImportError, ModuleNotFoundError):
        CONF_MAP_DEFAULT_WMS_STYLE = "niederschlagsradar"

_LOGGER = logging.getLogger(__name__)

# Number of parallel WMS fetch workers
_FETCH_WORKERS = 5

# WMS request timeout in seconds
_WMS_TIMEOUT = 25

# How long to cache model images before re-fetching (model runs update every ~3-6h)
_MODEL_CACHE_TTL = timedelta(hours=1)

_FRAME_NOT_PUBLISHED = object()


class FrameNotPublished(Exception):
    """Raised when the requested frame is not yet published by the WMS service."""


class FutureImageLoop:
    """Radar loop generator capable of displaying past, nowcast, and model forecast images.

    Caching strategy:
    - Past images (t < now):   Immutable observed radar data — cached forever until evicted from window.
    - Nowcast images (t > now, non-model): DWD recomputes with fresh radar every ~5 min — always re-fetched.
    - Model images:            Only change on new ICON-EU model runs (~3-6h) — cached for _MODEL_CACHE_TTL.

    WMS fetches are parallelized using ThreadPoolExecutor to keep update time under ~15 seconds.
    """

    def __init__(
        self,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        map_types: list[WeatherMapType | str],
        background_types: list[WeatherBackgroundMapType],
        steps_past: int = 6,
        steps_future: int = 0,
        hours_future: int = 0,
        speed: float = 0.5,
        speed_future: float = 2.0,
        image_width: int = 520,
        image_height: int = 580,
        markers: list[Marker] = [],
        dark_mode: bool = False,
    ):
        self._minx = minx
        self._miny = miny
        self._maxx = maxx
        self._maxy = maxy
        self._map_types = map_types
        self._background_types = background_types
        self._steps_past = int(steps_past)
        self._steps_future = int(steps_future)
        self._hours_future = int(hours_future)
        self._speed = float(speed)
        self._speed_future = float(speed_future)
        self._image_width = image_width
        self._image_height = image_height
        self.markers = markers
        self.dark_mode = dark_mode

        # Cache for immutable past images (radar) — keyed by timestamp
        self._past_cache: dict[datetime, ImageFile.ImageFile] = {}

        # Cache for model forecast images — only valid for _MODEL_CACHE_TTL
        self._model_cache: dict[datetime, ImageFile.ImageFile] = {}
        self._model_cache_time: datetime | None = None

        self._images: list[ImageFile.ImageFile] = []
        self._last_now: datetime | None = None
        self._last_complete = False
        self._model_times: set[datetime] = set()
        self._all_times: list[datetime] = []
        # Actual valid-time of the image data shown at each slot in _all_times.
        # Differs from _all_times when a fallback/stale image is used because the
        # real frame for that slot has not been published by DWD yet.
        self._display_times: list[datetime] = []
        self._not_published_times: dict[datetime, set[datetime]] = {}

        # NOTE: Do NOT call self.update() here.
        # WMS fetching is deferred to the first explicit update() call,
        # which runs on a background executor thread and does not block HA startup.

    def __getitem__(self, key):
        return self._images[key]

    def get_images(self) -> Iterable[ImageFile.ImageFile]:
        return self._images

    def update(self) -> None:
        """Update and rebuild the radar/nowcast/forecast loop image lists."""
        now = get_time_last_5_min(datetime.now(timezone.utc))

        if self._last_now == now and self._last_complete:
            _LOGGER.debug("Skipping map loop rebuild for unchanged slot %s", now)
            return

        previous_now = self._last_now
        self._last_now = now
        if previous_now != now:
            self._not_published_times = {}
        not_published_times = set(self._not_published_times.get(now, set()))

        # --- Calculate all required timestamps ---
        # Past: steps_past-1 frames before now (not including now itself)
        past_times = [
            now - timedelta(minutes=5 * i) for i in range(self._steps_past - 1, 0, -1)
        ]
        # Nowcast: 5-min steps into the future
        nowcast_times = [
            now + timedelta(minutes=5 * i) for i in range(1, self._steps_future + 1)
        ]

        # Model times: starting at next full hour after end of nowcast
        last_nowcast = nowcast_times[-1] if nowcast_times else now
        start_model = last_nowcast.replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(hours=1)
        model_times = [
            start_model + timedelta(hours=i) for i in range(self._hours_future)
        ]

        self._model_times = set(model_times)

        # Determine repeat count for model frames (slower display speed)
        repeat_count = max(1, round(self._speed_future / self._speed))

        # Build the full loop timeline (model frames repeated for slower display)
        loop_times: list[datetime] = []
        for t in past_times + [now] + nowcast_times:
            loop_times.append(t)
        for t in model_times:
            for _ in range(repeat_count):
                loop_times.append(t)

        self._all_times = loop_times

        # Unique timestamps that need an image (de-duplicated but ordered)
        seen: set[datetime] = set()
        unique_times: list[datetime] = []
        for t in loop_times:
            if t not in seen:
                seen.add(t)
                unique_times.append(t)

        # --- Determine model cache validity ---
        model_cache_expired = (
            self._model_cache_time is None
            or (now - self._model_cache_time) >= _MODEL_CACHE_TTL
        )
        if model_cache_expired:
            _LOGGER.debug("Model image cache expired — will re-fetch all model frames")
            self._model_cache.clear()
            self._model_cache_time = now

        # --- Classify each timestamp: cached or needs fetch ---
        already_have: dict[datetime, ImageFile.ImageFile] = {}
        to_fetch: list[datetime] = []

        for t in unique_times:
            if t < now and t in self._past_cache:
                # Past radar images are immutable — reuse from cache
                already_have[t] = self._past_cache[t]
            elif t in self._model_times and t in self._model_cache:
                # Model image cached and still valid
                already_have[t] = self._model_cache[t]
            elif t in not_published_times:
                continue
            else:
                # Must fetch: now, all nowcast (change every 5 min), new/expired model, new past
                to_fetch.append(t)

        _LOGGER.info(
            "Map update: now=%s, window=[%s -> %s], %d cached, %d to fetch (past cache: %d, model cache: %d)",
            now,
            unique_times[0].strftime("%H:%M") if unique_times else "?",
            unique_times[-1].strftime("%H:%M") if unique_times else "?",
            len(already_have),
            len(to_fetch),
            len(self._past_cache),
            len(self._model_cache),
        )

        # --- Fetch missing images in parallel ---
        fetched: dict[datetime, ImageFile.ImageFile] = {}
        if to_fetch:
            with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as executor:
                futures = {
                    executor.submit(self._get_image_safe, t): t for t in to_fetch
                }
                for future in as_completed(futures):
                    t = futures[future]
                    result = future.result()
                    if result is _FRAME_NOT_PUBLISHED:
                        not_published_times.add(t)
                    elif result is not None:
                        fetched[t] = result

        # --- Merge results ---
        new_images: dict[datetime, ImageFile.ImageFile] = {}
        new_images.update(already_have)
        new_images.update(fetched)
        self._last_complete = all(
            t in new_images or t in not_published_times for t in unique_times
        )

        # If now and previous observed radar frame are identical, keep only the
        # previous one when future playback is enabled. This avoids a visual
        # duplicate at the past/future boundary when DWD has not published a
        # distinct "now" radar raster yet.
        if self._steps_future > 0:
            previous_observed = now - timedelta(minutes=5)
            if now in new_images and previous_observed in new_images:
                if self._images_equal(new_images[now], new_images[previous_observed]):
                    del new_images[now]
                    _LOGGER.debug(
                        "Dropping duplicate now frame at %s (same as %s)",
                        now,
                        previous_observed,
                    )

        # --- Fill any gaps with nearest-neighbor fallback ---
        # actual_time_for tracks the real valid-time of the image data used for
        # each slot, which can differ from the slot's nominal time when a
        # fallback/stale image had to be used (e.g. DWD hasn't published the
        # current frame yet).
        actual_time_for: dict[datetime, datetime] = {
            t: t for t in new_images
        }
        for t in unique_times:
            if t not in new_images:
                # Try to find nearest available image for past timestamps only.
                # Current and future times should remain absent rather than showing
                # a stale image from a different moment.
                fallback = self._find_fallback(t, new_images, now)
                if fallback is not None:
                    fallback_image, fallback_time = fallback
                    new_images[t] = fallback_image
                    actual_time_for[t] = fallback_time
                    _LOGGER.debug(
                        "Using fallback image from %s for timestamp %s",
                        fallback_time,
                        t,
                    )

        # --- Update caches ---
        # Past cache: store all past images (immutable)
        for t in past_times:
            if t in new_images:
                self._past_cache[t] = new_images[t]
        # Evict past cache entries that are no longer in the window
        current_past_set = set(past_times)
        stale_past = [t for t in self._past_cache if t not in current_past_set]
        for t in stale_past:
            del self._past_cache[t]

        # Model cache: store all successfully fetched model images
        for t in model_times:
            if t in new_images:
                self._model_cache[t] = new_images[t]
        # Evict model cache entries that are no longer in the model window
        current_model_set = set(model_times)
        stale_model = [t for t in self._model_cache if t not in current_model_set]
        for t in stale_model:
            del self._model_cache[t]
        self._not_published_times[now] = not_published_times

        # --- Build final image list and matching timeline (with repeated model frames) ---
        available_times = [t for t in loop_times if t in new_images]
        self._all_times = available_times
        self._images = [new_images[t] for t in available_times]
        self._display_times = [
            actual_time_for.get(t, t) for t in available_times
        ]

    def _images_equal(
        self,
        first: ImageFile.ImageFile,
        second: ImageFile.ImageFile,
    ) -> bool:
        """Return True when two rendered frames are pixel-identical."""
        try:
            return (
                first.mode == second.mode
                and first.size == second.size
                and first.tobytes() == second.tobytes()
            )
        except Exception:
            return False

    def _find_fallback(
        self,
        t: datetime,
        available: dict[datetime, ImageFile.ImageFile],
        now: datetime | None = None,
    ) -> tuple[ImageFile.ImageFile, datetime] | None:
        """Find the nearest available image to timestamp t for past frames only.

        Returns the fallback image together with the timestamp it actually
        represents, so callers can display the real valid-time of the data
        instead of the (unpublished) nominal slot time.
        """
        if not available:
            return None
        if now is not None and t >= now:
            return None
        step = timedelta(hours=1) if t in self._model_times else timedelta(minutes=5)
        # Look backward up to 12 steps
        curr = t
        for _ in range(12):
            curr -= step
            if curr in available:
                return available[curr], curr
        # Fall back to last available
        last_time = list(available.keys())[-1]
        return available[last_time], last_time

    def _get_image_safe(self, date: datetime) -> ImageFile.ImageFile | None:
        """Fetch a single WMS image, returning None on failure instead of raising."""
        try:
            return self._get_image(date)
        except FrameNotPublished:
            _LOGGER.debug("Weather image for %s is not published yet", date)
            return _FRAME_NOT_PUBLISHED
        except Exception as e:
            _LOGGER.warning("Could not fetch weather image for %s: %s", date, e)
            return None

    def _get_image(self, date: datetime) -> ImageFile.ImageFile:
        # Determine if we should request the model forecast or radar/nowcast layer
        if date in self._model_times:
            map_layers = "dwd:Icon-eu_reg00625_fd_sl_TOTPREC01H"
        else:
            map_layers = ",".join(
                map_type.value if hasattr(map_type, "value") else str(map_type)
                for map_type in self._map_types
            )

        # Separate special layers and others for background types
        special_layers = [
            layer.value
            for layer in self._background_types
            if layer
            in [
                WeatherBackgroundMapType.SATELLIT,
                WeatherBackgroundMapType.KREISE,
                WeatherBackgroundMapType.GEMEINDEN,
            ]
        ]
        other_layers = [
            layer.value
            for layer in self._background_types
            if layer
            not in [
                WeatherBackgroundMapType.SATELLIT,
                WeatherBackgroundMapType.KREISE,
                WeatherBackgroundMapType.GEMEINDEN,
            ]
        ]
        # Combine layers: special first, then map type, then others
        layers = (
            f"{','.join(special_layers)},{map_layers},{','.join(other_layers)}".lstrip(
                ","
            ).rstrip(",")
        )

        # Build style list matching the layers list exactly
        layer_styles = []
        for _ in special_layers:
            layer_styles.append("")
        for _ in range(len(self._map_types)):
            if date in self._model_times:
                layer_styles.append("niederschlagsradar")
            else:
                layer_styles.append("")
        for _ in other_layers:
            layer_styles.append("")
        styles = ",".join(layer_styles)

        bgcolor = "0xFFFFFF"
        if self.dark_mode:
            bgcolor = "0x1C1C1C"

        url = (
            f"https://maps.dwd.de/geoserver/dwd/wms?service=WMS&version=1.3.0"
            f"&request=GetMap&layers={layers}&bbox={self._miny},{self._minx},{self._maxy},{self._maxx}"
            f"&width={self._image_width}&height={self._image_height}&srs=EPSG:4326&styles={styles}&format=image/png"
            f"&TIME={date.strftime('%Y-%m-%dT%H:%M:00.0Z')}&bgcolor={bgcolor}"
        )

        _LOGGER.debug("Requesting WMS URL: %s", url)
        request = requests.get(url, timeout=_WMS_TIMEOUT)
        if request.status_code != 200:
            raise ConnectionError(
                f"Error during image request from DWD servers (HTTP {request.status_code}): {url}"
            )
        content_type = request.headers.get("content-type")
        if content_type != "image/png":
            if (
                content_type is not None
                and content_type.startswith("text/xml")
                and b"<ServiceException" in request.content
            ):
                raise FrameNotPublished(
                    f"Frame not published for {date.strftime('%Y-%m-%dT%H:%M:00.0Z')}"
                )
            raise TypeError(
                f"Unexpected content type: {content_type}"
            )
        try:
            image = Image.open(BytesIO(request.content))
        except Exception as e:
            raise RuntimeError(f"Error during image parsing: {url}") from e

        image = draw_marker(
            image,
            ImageBoundaries(self._minx, self._maxx, self._miny, self._maxy),
            self.markers,
        )
        return image
