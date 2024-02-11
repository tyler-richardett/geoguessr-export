from loguru import logger
from notion_client import Client
from notion_client.helpers import collect_paginated_api
from strenum import StrEnum

from geoguessr_export import geoguessr
from geoguessr_export.databricks import get_env_variable


class NotionDatabases(StrEnum):
    DAILY_CHALLENGES = "98b9b311-63c7-48d7-9113-0865077b6606"
    ROUNDS = "223cf4fd-f210-40c0-8640-14adc6df36c1"
    COUNTRIES = "46012741-8bfe-4a62-968f-4c206c726fb0"
    MEDALS = "a45aac7d-71cc-4b4f-a032-e43f66ba4382"


class NotionProperties(StrEnum):
    CHALLENGE_ID = "Challenge ID"
    DATE = "Date"
    DATE_ = "[Date]"
    MEDAL = "Medal"
    ROUND = "Round"
    LOCATION_LATITUDE = "Latitude"
    LOCATION_LONGITUDE = "Longitude"
    PANORAMA_ID = "Panorama ID"
    HEADING = "Heading"
    PITCH = "Pitch"
    ZOOM = "Zoom"
    COUNTRY = "Country"
    GUESS_LATITUDE = "Guess Latitude"
    GUESS_LONGITUDE = "Guess Longitude"
    DISTANCE = "Distance (miles)"
    POINTS = "Points"
    TIME = "Time (seconds)"
    DAILY_CHALLENGE = "Daily Challenge"


class NotionIcons(StrEnum):
    GLOBE = "https://www.notion.so/icons/geography_gray.svg"
    MAP_PIN = "https://www.notion.so/icons/map-pin-alternate_gray.svg"
    PASSPORT = "https://www.notion.so/icons/passport_gray.svg"


class Notion:
    def __init__(self, token: str | None = None):
        self._client = Client(auth=token or get_env_variable("NOTION_TOKEN"))
        self._medal_lookup = self._create_lookup(database_id=NotionDatabases.MEDALS)
        self._country_lookup = self._create_lookup(database_id=NotionDatabases.COUNTRIES)
        self._daily_challenges_lookup = self._create_lookup(
            database_id=NotionDatabases.DAILY_CHALLENGES, property_key=NotionProperties.CHALLENGE_ID
        )

    def _create_lookup(self, database_id: str, property_key: str = "Name") -> dict[str, str]:
        items: list[dict] = collect_paginated_api(self._client.databases.query, database_id=database_id)

        lookup = {}
        for item in items:
            _properties: dict = item.get("properties")
            _property: dict = _properties.get(property_key)
            _attribute: list[dict] = _property.get("title") or _property.get("rich_text")

            name = _attribute[0].get("plain_text")
            item_id = item.get("id")

            lookup.update({name: item_id})

        return lookup

    def _add_rounds(self, daily_challenge: geoguessr.DailyChallenge, challenge_page_id: str) -> None:
        for idx, _round in enumerate(daily_challenge.rounds, start=1):
            logger.info(f"[{daily_challenge.challenge_id}] Adding round {idx} score to Notion...")

            properties = {
                NotionProperties.ROUND: {
                    "title": [{"text": {"content": f"Round {idx}"}}],
                },
                NotionProperties.LOCATION_LATITUDE: {"number": round(_round.location.latitude, 4)},
                NotionProperties.LOCATION_LONGITUDE: {"number": round(_round.location.longitude, 4)},
                NotionProperties.HEADING: {"number": _round.location.heading},
                NotionProperties.PITCH: {"number": _round.location.pitch},
                NotionProperties.ZOOM: {"number": _round.location.zoom},
                NotionProperties.GUESS_LATITUDE: {"number": round(_round.guess.latitude, 4)},
                NotionProperties.GUESS_LONGITUDE: {"number": round(_round.guess.longitude, 4)},
                NotionProperties.DISTANCE: {"number": _round.guess.distance_mi},
                NotionProperties.POINTS: {"number": _round.guess.points_earned},
                NotionProperties.TIME: {"number": _round.guess.time_seconds},
                NotionProperties.DATE: {"relation": [{"id": challenge_page_id}]},
            }

            if _round.location.pano_id:
                properties.update(
                    {
                        NotionProperties.PANORAMA_ID: {"rich_text": [{"text": {"content": _round.location.pano_id}}]},
                    }
                )

            if _round.location.country.name:
                if _round.location.country.name not in self._country_lookup:
                    logger.info(
                        f"[{daily_challenge.challenge_id}] Adding country {_round.location.country.name} to Notion..."
                    )

                    _page: dict = self._client.pages.create(
                        parent={"database_id": NotionDatabases.COUNTRIES},
                        icon={"emoji": _round.location.country.flag},
                        properties={
                            "Name": {"title": [{"text": {"content": _round.location.country.name}}]},
                        },
                    )
                    _page_id = _page.get("id")
                    self._country_lookup.update({_round.location.country.name: _page_id})

                    logger.info(
                        f"[{daily_challenge.challenge_id}] Successfully added country {_round.location.country.name} to Notion."
                    )

                properties.update(
                    {
                        NotionProperties.COUNTRY: {
                            "relation": [{"id": self._country_lookup.get(_round.location.country.name)}],
                        },
                    }
                )

            _ = self._client.pages.create(
                parent={"database_id": NotionDatabases.ROUNDS},
                icon={"external": {"url": NotionIcons.MAP_PIN}},
                properties=properties,
            )

            logger.info(f"[{daily_challenge.challenge_id}] Successfully added round {idx} score to Notion.")

    def add_daily_challenges(self, daily_challenges: list[geoguessr.DailyChallenge]) -> None:
        for _daily_challenge in daily_challenges:
            if _daily_challenge.challenge_id in self._daily_challenges_lookup:
                logger.warning(f"Daily challenge {_daily_challenge.challenge_id} already exists in Notion, skipping.")
                continue

            logger.info(f"Adding daily challenge {_daily_challenge.challenge_id} to Notion...")
            properties = {
                NotionProperties.DATE: {
                    "title": [
                        {"mention": {"date": {"start": _daily_challenge.completed_datetime_utc.strftime("%Y-%m-%d")}}}
                    ],
                },
                NotionProperties.DATE_: {
                    "date": {"start": _daily_challenge.completed_datetime_utc.strftime("%Y-%m-%d")},
                },
                NotionProperties.CHALLENGE_ID: {
                    "rich_text": [{"text": {"content": _daily_challenge.challenge_id}}],
                },
                NotionProperties.MEDAL: {"relation": [{"id": self._medal_lookup.get(_daily_challenge.medal)}]},
            }

            _page: dict = self._client.pages.create(
                parent={"database_id": NotionDatabases.DAILY_CHALLENGES},
                icon={"external": {"url": NotionIcons.GLOBE}},
                properties=properties,
            )

            _page_id = _page.get("id")
            self._add_rounds(_daily_challenge, _page_id)

            logger.info(f"Successfully added daily challenge {_daily_challenge.challenge_id} to Notion.")
