from __future__ import annotations

import os
from io import BytesIO

import requests
from PIL import Image
from strenum import StrEnum

from geoguessr_export.geoguessr import GeoguessrIcons, Guess, Location


class GoogleMapsEndpoints(StrEnum):
    STREETVIEW = "/maps/api/streetview"
    STATIC_MAP = "/maps/api/staticmap"


class GoogleMaps:
    BASE_URL = "https://maps.googleapis.com"

    def __init__(self, api_key: str | None = None):
        self._session = requests.Session()
        self._session.params.update({"key": os.environ.get("GOOGLE_API_KEY") or api_key})

    def _get_streetview(
        self, location: Location, heading: int, crop_bottom: int, width: int, height: int, pitch: int
    ) -> Image:
        r = self._session.get(
            self.BASE_URL + GoogleMapsEndpoints.STREETVIEW,
            params={
                "size": f"{width}x{height}",
                "location": f"{location.latitude},{location.longitude}",
                "heading": heading,
                "pitch": pitch,
            },
        )
        r.raise_for_status()

        image = Image.open(BytesIO(r.content))
        image_cropped = image.crop(box=(0, 0, width, height - crop_bottom))

        return image_cropped

    def _get_streetview_pano(
        self,
        location: Location,
        crop_bottom: int = 25,
        width: int = 640,
        height: int = 640,
        pitch: int = 0,
    ) -> Image:
        image_pano = Image.new("RGB", (width * 4, height - crop_bottom))

        for idx, heading in enumerate([270, 0, 90, 180]):
            image = self._get_streetview(
                latitude=location.latitude,
                longitude=location.longitude,
                heading=heading,
                crop_bottom=crop_bottom,
                width=width,
                height=height,
                pitch=pitch,
            )

            image_pano.paste(image, (idx * width, 0))

        return image_pano

    def _get_static_map(
        self,
        location: Location,
        guess: Guess,
        width: int = 625,
        height: int = 625,
        zoom: int = 5,
    ) -> Image:
        r = self._session.get(
            self.BASE_URL + GoogleMapsEndpoints.STATIC_MAP,
            params={
                "size": f"{width}x{height}",
                "center": f"{location.latitude},{location.longitude}",
                "zoom": zoom,
                "maptype": "roadmap",
                "markers": [
                    f"icon:{GeoguessrIcons.GUESS}|{guess.latitude},{guess.longitude}",
                    f"icon:{GeoguessrIcons.LOCATION}|{location.latitude},{location.longitude}",
                ],
            },
        )
        r.raise_for_status()

        image = Image.open(BytesIO(r.content))

        return image
