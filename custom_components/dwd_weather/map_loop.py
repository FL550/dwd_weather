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

_LOGGER = logging.getLogger(__name__)


class FutureImageLoop:
    """Radar loop generator capable of displaying past, nowcast, and model forecast images."""

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
        self._steps_past = steps_past
        self._steps_future = steps_future
        self._hours_future = hours_future
        self._image_width = image_width
        self._image_height = image_height
        self.markers = markers
        self.dark_mode = dark_mode

        self._cached_images: dict[datetime, ImageFile.ImageFile] = {}
        self._images: list[ImageFile.ImageFile] = []
        self._last_now: datetime | None = None
        self._model_times: set[datetime] = set()
        self._all_times: list[datetime] = []

        self.update()

    def __getitem__(self, key):
        return self._images[key]

    def get_images(self) -> Iterable[ImageFile.ImageFile]:
        return self._images

    def update(self):
        now = get_time_last_5_min(datetime.now(timezone.utc))

        if self._last_now == now:
            # We don't need to rebuild if now hasn't advanced, unless our cache is empty
            if self._images:
                return

        self._last_now = now

        # Calculate all required timestamps
        past_times = [
            now - timedelta(minutes=5 * i) for i in range(self._steps_past - 1, 0, -1)
        ]
        nowcast_times = [
            now + timedelta(minutes=5 * i) for i in range(1, self._steps_future + 1)
        ]

        # Calculate model times (starting at the next hour after the end of nowcast)
        last_nowcast = nowcast_times[-1] if nowcast_times else now
        start_model = last_nowcast.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        model_times = [
            start_model + timedelta(hours=i) for i in range(self._hours_future)
        ]

        self._model_times = set(model_times)
        all_times = past_times + [now] + nowcast_times + model_times
        self._all_times = all_times

        new_images: dict[datetime, ImageFile.ImageFile] = {}
        for t in all_times:
            # Past and current times can be cached
            if t <= now and t in self._cached_images:
                new_images[t] = self._cached_images[t]
            else:
                try:
                    # Fetch fresh (especially future times, which update dynamically)
                    new_images[t] = self._get_image(t)
                except Exception as e:
                    _LOGGER.warning("Could not fetch weather image for time %s: %s", t, e)
                    # If fetching a future image fails, try to use a previous frame
                    # to keep the loop complete, or fall back to cached version
                    prev_t = t - (timedelta(hours=1) if t in self._model_times else timedelta(minutes=5))
                    if prev_t in new_images:
                        new_images[t] = new_images[prev_t]
                    elif t in self._cached_images:
                        new_images[t] = self._cached_images[t]

        self._cached_images = new_images
        self._images = [
            self._cached_images[t] for t in all_times if t in self._cached_images
        ]

    def _get_image(self, date: datetime) -> ImageFile.ImageFile:
        # Determine if we should request the model forecast or radar nowcast layer
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
        # Combine layers with special layers first, then map types, then other layers
        layers = (
            f"{','.join(special_layers)},{map_layers},{','.join(other_layers)}".lstrip(
                ","
            ).rstrip(",")
        )
        bgcolor = "0xFFFFFF"
        if self.dark_mode:
            bgcolor = "0x1C1C1C"

        url = (
            f"https://maps.dwd.de/geoserver/dwd/wms?service=WMS&version=1.3.0"
            f"&request=GetMap&layers={layers}&bbox={self._miny},{self._minx},{self._maxy},{self._maxx}"
            f"&width={self._image_width}&height={self._image_height}&srs=EPSG:4326&styles=&format=image/png"
            f"&TIME={date.strftime('%Y-%m-%dT%H:%M:00.0Z')}&bgcolor={bgcolor}"
        )

        request = requests.get(url, timeout=15)
        if request.status_code != 200:
            raise ConnectionError(
                f"Error during image request from DWD servers (HTTP {request.status_code}): {url}"
            )
        elif request.headers.get("content-type") != "image/png":
            raise TypeError(
                f"Unexpected content type: {request.headers.get('content-type')}"
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
