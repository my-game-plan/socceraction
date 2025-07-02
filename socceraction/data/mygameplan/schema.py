"""SPADL schema for MyGamePlan data."""

from socceraction.data.schema import (
    CompetitionSchema,
    EventSchema,
    GameSchema,
    PlayerSchema,
    TeamSchema,
)


class MyGamePlanCompetitionSchema(CompetitionSchema):
    """Definition of a dataframe containing a list of competitions and seasons."""


class MyGamePlanGameSchema(GameSchema):
    """Definition of a dataframe containing a list of games."""


class MyGamePlanPlayerSchema(PlayerSchema):
    """Definition of a dataframe containing the list of players of a game."""


class MyGamePlanTeamSchema(TeamSchema):
    """Definition of a dataframe containing the list of teams of a game."""


class MyGamePlanEventSchema(EventSchema):
    """Definition of a dataframe containing event stream data of a game."""
