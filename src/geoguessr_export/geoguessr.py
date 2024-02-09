from __future__ import annotations

import json
from datetime import datetime, timedelta

import pycountry
import requests
from dateutil.parser import parse
from loguru import logger
from pydantic import BaseModel, computed_field
from strenum import StrEnum

from geoguessr_export.databricks import get_env_variable


class GeoguessrEndpoints(StrEnum):
    MY_ACTIVITIES = "/api/v4/feed/private"
    GAME_RESULTS = "/api/v3/results/highscores"


class GeoguessrIcons(StrEnum):
    LOCATION = (
        "https://www.geoguessr.com/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fcorrect-location.56f20eda.png&w=32&q=75"
    )
    GUESS = "https://www.geoguessr.com/_next/static/media/favicon.bffdd9d3.png"


class Country(BaseModel):
    code: str

    @computed_field
    @property
    def name(self) -> str:
        return pycountry.countries.get(alpha_2=self.code).name


class Location(BaseModel):
    latitude: float
    longitude: float
    pano_id: str
    heading: int
    pitch: int
    zoom: int
    country: Country


class Guess(BaseModel):
    latitude: float
    longitude: float
    points_earned: int
    distance_mi: float
    time_seconds: int


class Round(BaseModel):
    location: Location
    guess: Guess


class DailyChallenge(BaseModel):
    challenge_id: str
    completed_datetime_utc: datetime
    points_earned: int
    rounds: list[Round]


class Geoguessr:
    BASE_URL = "https://www.geoguessr.com"

    def __init__(self, ncfa_token: str | None = None):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }
        )
        self._session.cookies.set("_ncfa", get_env_variable("GEOGUESSR_TOKEN") or ncfa_token)

    def _get_challenge(self, challenge_id: str) -> dict:
        logger.info(f"Retrieving results from daily challenge ID {challenge_id}...")

        r = self._session.get(
            url=self.BASE_URL + GeoguessrEndpoints.GAME_RESULTS + f"/{challenge_id}",
            params={"friends": "true", "limit": "26", "minRounds": "5"},
        )
        r.raise_for_status()

        challenge: dict = r.json()
        items: list[dict] = challenge.get("items")
        game: dict = items[0].get("game")

        logger.info(f"Successfully retrieved results from daily challenge ID {challenge_id}.")

        return game

    def _get_rounds(self, challenge_id: str) -> list[Round]:
        game = self._get_challenge(challenge_id)

        locations = Geoguessr._extract_locations(game)
        guesses = Geoguessr._extract_guesses(game)

        rounds = []
        for location, guess in zip(locations, guesses):
            rounds.append(Round(location=location, guess=guess))

        return rounds

    @staticmethod
    def _extract_locations(game: dict) -> list[Location]:
        logger.info("Extracting locations from daily challenge...")

        _rounds: list[dict] = game.get("rounds")

        locations = []
        for _round in _rounds:
            locations.append(
                Location(
                    latitude=_round.get("lat"),
                    longitude=_round.get("lng"),
                    pano_id=_round.get("panoId"),
                    heading=_round.get("heading"),
                    pitch=_round.get("pitch"),
                    zoom=_round.get("zoom"),
                    country=Country(code=_round.get("streakLocationCode")),
                )
            )

        logger.info("Successfully extracted locations from daily challenge.")

        return locations

    @staticmethod
    def _extract_guesses(game: dict) -> list[Guess]:
        logger.info("Extracting guesses from daily challenge...")

        _player: dict = game.get("player")
        _guesses: list[dict] = _player.get("guesses")

        guesses = []
        for _guess in _guesses:
            _score: dict = _guess.get("roundScore")
            _distance: dict = _guess.get("distance")
            _distance_mi: dict = _distance.get("miles")

            guesses.append(
                Guess(
                    latitude=_guess.get("lat"),
                    longitude=_guess.get("lng"),
                    points_earned=_score.get("amount"),
                    distance_mi=_distance_mi.get("amount"),
                    time_seconds=_guess.get("time"),
                )
            )

        logger.info("Successfully extracted guesses from daily challenge.")

        return guesses

    def _get_challenges(self, past_n_days: int = 1) -> list[DailyChallenge]:
        pagination_token = None
        keep_going = True
        page_idx = 1

        daily_challenges = []

        while keep_going:
            logger.info(f"Polling page {page_idx} of My Activities for new daily challenge results...")
            if pagination_token:
                r = self._session.get(
                    url=self.BASE_URL + GeoguessrEndpoints.MY_ACTIVITIES, params={"paginationToken": pagination_token}
                )
            else:
                r = self._session.get(url=self.BASE_URL + GeoguessrEndpoints.MY_ACTIVITIES)

            r.raise_for_status()
            r_json: dict = r.json()

            pagination_token = r_json.get("paginationToken")
            if pagination_token is None:
                keep_going = False

            entries: list[dict] = r_json.get("entries", [])

            for entry in entries:
                completed_datetime_utc = parse(entry.get("time"), ignoretz=True)
                if completed_datetime_utc < datetime.utcnow() - timedelta(days=past_n_days):
                    logger.info("Reached end of date range, exiting.")
                    keep_going = False
                    break

                _payload = entry.get("payload")
                payload = json.loads(_payload)

                if not isinstance(payload, dict):
                    continue

                if payload.get("isDailyChallenge") is True or (
                    payload.get("isDailyChallenge") is None
                    and payload.get("challengeToken") is not None
                    and payload.get("mapName") == "World"
                ):
                    challenge_id = payload.get("challengeToken")
                    rounds = self._get_rounds(challenge_id)

                    challenge = DailyChallenge(
                        completed_datetime_utc=completed_datetime_utc,
                        points_earned=payload.get("points"),
                        challenge_id=challenge_id,
                        rounds=rounds,
                    )
                    daily_challenges.append(challenge)

            if pagination_token is None:
                logger.info("Reached end of My Activities pages, exiting.")

            page_idx += 1

        return daily_challenges

    def run(self):
        pass
