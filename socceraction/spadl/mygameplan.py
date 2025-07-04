"""MyGamePlan events to SPADL converter."""

from typing import Optional, cast

import pandas as pd
from pandera.typing import DataFrame

from . import config as spadlconfig
from .base import _fix_clearances, _fix_direction_of_play
from .schema import SPADLSchema

MGP_TO_SOCCERACTION_X = 1.05
MGP_TO_SOCCERACTION_Y = 0.68


class MyGamePlanEvent(dict):
    """A class representing a MyGamePlan event."""

    def __getattr__(self, name: str) -> any:
        """Retrieve the value of the specified attribute.

        If the attribute does not exist, return None. If the value is a dictionary,
        wrap it in a MyGamePlanEvent instance.

        Parameters
        ----------
        name : str
        The name of the attribute to retrieve.

        Returns
        -------
        Optional[Any]
        The value of the attribute, or None if it does not exist.
        """
        try:
            value = self[name]
            if isinstance(value, dict):
                return MyGamePlanEvent(value)  # Wrap nested dictionaries
            return value
        except KeyError:
            return None


def convert_to_actions(
    events: list[MyGamePlanEvent],
) -> DataFrame[SPADLSchema]:
    """Convert a MyGamePlan event data set to SPADL actions.

    Parameters
    ----------
    dataset : EventDataset
        A Kloppy event data set.
    game_id : str or int, optional
        The identifier of the game. If not provided, the game id will not be
        set in the SPADL DataFrame.

    Returns
    -------
    actions : pd.DataFrame
        DataFrame with corresponding SPADL actions.

    """
    # Convert the events to SPADL actions
    actions = []
    for event in events:
        action = dict(
            game_id=event.match._id,
            original_event_id=event._id,
            period_id=event.period,
            time_seconds=event.timestamp,
            team_id=event.team._id if event.team else None,
            player_id=event.player._id if event.player else None,
            start_x=event.coordinates[1] * MGP_TO_SOCCERACTION_X if event.coordinates else None,
            start_y=event.coordinates[0] * MGP_TO_SOCCERACTION_Y if event.coordinates else None,
            **_get_end_location(event),
            **_parse_event(event),
        )
        actions.append(action)

    df_actions = (
        pd.DataFrame(actions)
        .loc[lambda df: df["type_id"] != spadlconfig.actiontypes.index("non_action")]
        .sort_values(["game_id", "period_id", "time_seconds"], kind="mergesort")
        .reset_index(drop=True)
    )

    home_team_id = events[0]["match"]["home_team"]["_id"]
    df_actions = _fix_direction_of_play(df_actions, home_team_id)
    df_actions = _fix_clearances(df_actions)

    df_actions["action_id"] = range(len(df_actions))
    return cast(DataFrame[SPADLSchema], df_actions)


def _get_end_location(event: MyGamePlanEvent) -> dict[str, Optional[float]]:
    if event.event_type == "pass":
        if event.get("pass"):
            return {
                "end_x": event.get("pass").get("end_coordinates")[1] * MGP_TO_SOCCERACTION_X,
                "end_y": event.get("pass").get("end_coordinates")[0] * MGP_TO_SOCCERACTION_Y,
            }
    elif event.event_type == "shot":
        if event.get("shot").get("shot_coordinate_y"):
            return {
                "end_x": 105,
                "end_y": event.get("shot").get("shot_coordinate_y") * MGP_TO_SOCCERACTION_Y,
            }
        else:
            return {
                "end_x": event.coordinates[1] * MGP_TO_SOCCERACTION_X
                if event.coordinates
                else None,
                "end_y": event.coordinates[0] * MGP_TO_SOCCERACTION_Y
                if event.coordinates
                else None,
            }
    elif event.event_type == "carry":
        if event.get("carry"):
            return {
                "end_x": event.get("carry").get("end_coordinates")[1] * MGP_TO_SOCCERACTION_X,
                "end_y": event.get("carry").get("end_coordinates")[0] * MGP_TO_SOCCERACTION_Y,
            }

    if event.coordinates:
        return {"end_x": event.coordinates[1], "end_y": event.coordinates[0]}
    return {"end_x": None, "end_y": None}


def _parse_event(event: MyGamePlanEvent) -> dict[str, int]:
    events = {
        "pass": _parse_pass_event,
        "shot": _parse_shot_event,
        "carry": _parse_carry_event,
        "foul": _parse_foul_event,
        "duel": _parse_duel_event,
        "clearance": _parse_clearance_event,
        "keeper_defensive_action": _parse_goalkeeper_event,
        "interception": _parse_interception_event,
        "recovery": _parse_interception_event,
        "dribble": _parse_take_on_event,
    }
    parser = events.get(event.event_type, _parse_event_as_non_action)
    a, r, b = parser(event)
    return {
        "type_id": spadlconfig.actiontypes.index(a),
        "result_id": spadlconfig.results.index(r),
        "bodypart_id": spadlconfig.bodyparts.index(b),
    }


def _parse_pass_event(event: MyGamePlanEvent) -> tuple[str, str, str]:  # noqa: C901
    b = _parse_bodypart(event.get("pass", {}).get("body_part", None))

    secondary_event_types = event.get("secondary_event_types", []) or []
    set_piece_type = event.get("pass", {}).get("set_piece_type", None)
    pass_distance = event.get("pass", {}).get("distance", None)
    a = "pass"  # default
    r = None
    if set_piece_type == "throw_in":
        a = "throw_in"
        b = "other"
    elif set_piece_type == "goal_kick":
        a = "goalkick"
    elif set_piece_type == "corner_kick":
        if pass_distance is not None and pass_distance < 20:
            a = "corner_short"
        else:
            a = "corner_crossed"
    elif "cross" in secondary_event_types:
        a = "cross"
    elif "wide_free_kick" in secondary_event_types or "other_free_kick" in secondary_event_types:
        if pass_distance is not None and pass_distance < 20:
            a = "freekick_short"
        else:
            a = "freekick_crossed"
    else:
        a = "pass"

    if r is None:
        if event.result in ["incomplete", "out", "unsuccessful"]:
            r = "fail"
        elif event.result == "offside":
            r = "offside"
        elif event.result in ["successful", "complete"]:
            r = "success"
        else:
            # discard interrupted events
            a = "non_action"
            r = "success"

    return a, r, b


def _parse_bodypart(body_part: str, default: str = "foot") -> str:
    if body_part is None:
        return default
    if body_part == "head":
        return "head"
    elif body_part == "right_foot":
        return "foot_right"
    elif body_part == "left_foot":
        return "foot_left"
    elif body_part == "other":
        return "other"
    elif body_part is not None:
        return "other"
    return body_part


def _parse_shot_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    b = _parse_bodypart(event.get("shot", {}).get("body_part", None))

    set_piece_type = event.get("shot", {}).get("set_piece_type", None)

    if set_piece_type in ["direct_free_kick", "indirect_free_kick"]:
        a = "shot_freekick"
    elif set_piece_type == "penalty":
        a = "shot_penalty"
    else:
        a = "shot"

    if event.result == "goal":
        r = "success"
    elif event.result == "own_goal":
        a = "bad_touch"
        r = "owngoal"
    else:
        r = "fail"

    return a, r, b


def _parse_carry_event(_e: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "dribble"
    r = "success"
    b = "foot"
    return a, r, b


def _parse_foul_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "foul"
    r = "fail"
    b = "foot"

    secondary_event_types = event.get("secondary_event_types", []) or []

    if "yellow_card" in secondary_event_types:
        r = "yellow_card"
    elif "red_card" in secondary_event_types:
        r = "red_card"

    return a, r, b


def _parse_duel_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    secondary_event_types = event.get("secondary_event_types", []) or []

    a = "non_action"
    b = "foot"
    if (
        "sliding_tackle" in secondary_event_types or "ground_duel" in secondary_event_types
    ) and "loose_ball_duel" not in secondary_event_types:
        a = "tackle"
        b = "foot"
    if event.result == "unsuccessful" or event.result == "lost":
        r = "fail"
    else:
        r = "success"

    return a, r, b


def _parse_clearance_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "clearance"
    r = "success"
    b = "foot"
    return a, r, b


def _parse_goalkeeper_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "non_action"
    r = "success"
    secondary_event_types = event.get("secondary_event_types", []) or []
    b = "other"

    if "save" in secondary_event_types:
        a = "keeper_save"
        r = "success"
    if "claim" in secondary_event_types:
        a = "keeper_claim"
    if "punch" in secondary_event_types:
        a = "keeper_punch"
    if "pick_up" in secondary_event_types:
        a = "keeper_pick_up"

    return a, r, b


def _parse_interception_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "interception"
    b = "foot"
    if event.result == "unsuccessful":
        r = "fail"
    else:
        r = "success"

    return a, r, b


def _parse_take_on_event(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "take_on"

    if event.result == "successful":
        r = "success"
    else:
        r = "fail"

    b = "foot"

    return a, r, b


def _parse_event_as_non_action(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "non_action"
    r = "success"
    b = "foot"
    return a, r, b
