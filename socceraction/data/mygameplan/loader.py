"""Implements serializers for MyGamePlan data."""

from typing import cast

import pandas as pd  # type: ignore
from pandera.typing import DataFrame
from pymongo import MongoClient

from socceraction.data.base import EventDataLoader

from .schema import (
    MyGamePlanCompetitionSchema,
    MyGamePlanEventSchema,
    MyGamePlanGameSchema,
    MyGamePlanPlayerSchema,
    MyGamePlanTeamSchema,
)


class MyGamePlanLoader(EventDataLoader):
    """Load MyGamePlan data.

    Parameters
    ----------
    connection_string: str
    """

    client: MongoClient

    def __init__(self, connection_string: str, db_name: str) -> None:
        self.client = MongoClient(connection_string)
        self.db = self.client[db_name]

    def competitions(self) -> DataFrame[MyGamePlanCompetitionSchema]:
        """Return a dataframe with all available competitions and seasons.

        Raises
        ------
        ParseError
            When the raw data does not adhere to the expected format.

        Returns
        -------
        pd.DataFrame
            A dataframe containing all available competitions and seasons. See
            :class:`~socceraction.spadl.statsbomb.MyGamePlanCompetitionSchema` for the schema.
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "competitions",
                    "localField": "competition_id",
                    "foreignField": "_id",
                    "as": "competition",
                }
            },
            {
                "$unwind": "$competition"  # assuming each competition_id matches exactly one competition
            },
            {
                "$project": {
                    "_id": 1,
                    "season_id": 1,
                    "competition_id": 1,
                    "competition_name": "$competition.name",
                }
            },
        ]

        db_competition_seasons = list(self.db["competition_seasons"].aggregate(pipeline))

        competitions = [
            {
                "season_id": cs["season_id"],
                "competition_id": cs["competition_id"],
                "competition_name": cs["competition_name"],
                "season_name": cs["season_id"],
            }
            for cs in db_competition_seasons
        ]
        return cast(DataFrame[MyGamePlanCompetitionSchema], pd.DataFrame(competitions))

    def games(self, competition_id: int, season_id: int) -> DataFrame[MyGamePlanGameSchema]:
        """Return a dataframe with all available games in a season.

        Parameters
        ----------
        competition_id : int
            The ID of the competition.
        season_id : int
            The ID of the season.

        Raises
        ------
        ParseError
            When the raw data does not adhere to the expected format.

        Returns
        -------
        pd.DataFrame
            A dataframe containing all available games. See
            :class:`~socceraction.spadl.mygameplan.MyGamePlanSchema` for the schema.
        """
        db_matches = list(
            self.db["matches"].find(
                {
                    "event_data_available": True,
                    "competition_id": competition_id,
                    "season_id": season_id,
                },
                {
                    "_id": 1,
                    "home_team._id": 1,
                    "away_team._id": 1,
                    "season_id": 1,
                    "competition_id": 1,
                    "date": 1,
                    "match_day": 1,
                },
            )
        )
        games = [
            {
                "game_id": match["_id"],
                "season_id": match["season_id"],
                "competition_id": match["competition_id"],
                "game_day": match["match_day"],
                "game_date": match["date"],
                "home_team_id": str(match["home_team"]["_id"]),
                "away_team_id": str(match["away_team"]["_id"]),
            }
            for match in db_matches
        ]
        return cast(DataFrame[MyGamePlanGameSchema], pd.DataFrame(games))

    def teams(self, game_id: str) -> DataFrame[MyGamePlanTeamSchema]:
        """Return a dataframe with both teams that participated in a game.

        Parameters
        ----------
        game_id : int
            The ID of the game.

        Raises
        ------
        ParseError  # noqa: DAR402
            When the raw data does not adhere to the expected format.

        Returns
        -------
        pd.DataFrame
            A dataframe containing both teams. See
            :class:`~socceraction.spadl.statsbomb.MyGamePlanTeamSchema` for the schema.
        """
        match = self.db["matches"].find_one(
            {"_id": game_id},
            {"home_team.name": 1, "away_team.name": 1, "home_team._id": 1, "away_team._id": 1},
        )
        teams = [
            {"team_id": str(match["home_team"]["_id"]), "team_name": match["home_team"]["name"]},
            {"team_id": str(match["away_team"]["_id"]), "team_name": match["away_team"]["name"]},
        ]
        return cast(DataFrame[MyGamePlanTeamSchema], pd.DataFrame(teams))

    def players(self, game_id: str) -> DataFrame[MyGamePlanPlayerSchema]:
        """Return a dataframe with all players that participated in a game.

        Parameters
        ----------
        game_id : int
            The ID of the game.

        Raises
        ------
        ParseError  # noqa: DAR402
            When the raw data does not adhere to the expected format.

        Returns
        -------
        pd.DataFrame
            A dataframe containing all players. See
            :class:`~socceraction.spadl.statsbomb.MyGamePlanPlayerSchema` for the schema.
        """
        match = self.db["matches"].find_one(
            {"_id": game_id},
            {
                "home_team._id": 1,
                "home_team.players": 1,
                "away_team._id": 1,
                "away_team.players": 1,
            },
        )
        players = []

        for team_key in ["home_team", "away_team"]:
            team = match[team_key]
            team_id = team["_id"]
            for p in team["players"]:
                players.append(
                    {
                        "game_id": game_id,
                        "team_id": team_id,
                        "player_id": p["_id"],
                        "player_name": p["name"],
                        "minutes_played": p.get("play_time", {}).get("minutes_played", 0),
                        "jersey_number": p.get("jersey_number", 0),
                    }
                )
        return cast(DataFrame[MyGamePlanPlayerSchema], pd.DataFrame(players))

    def events(self, game_id: str) -> DataFrame[MyGamePlanEventSchema]:
        """Return a dataframe with the event stream of a game.

        Parameters
        ----------
        game_id : int
            The ID of the game.

        Raises
        ------
        ParseError
            When the raw data does not adhere to the expected format.

        Returns
        -------
        pd.DataFrame
            A dataframe containing the event stream. See
            :class:`~socceraction.spadl.statsbomb.StatsBombEventSchema` for the schema.
        """
        events = (
            self.db["events"]
            .find({"match._id": game_id})
            .sort([("period", 1), ("timestamp", 1), ("event_type", -1)])
        )
        events_df = pd.DataFrame(events)

        # Replace NaN with None
        events_df = events_df.where(pd.notnull(events_df), None)

        return cast(DataFrame[MyGamePlanEventSchema], events_df)
