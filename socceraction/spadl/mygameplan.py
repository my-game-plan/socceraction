"""MyGamePlan events to SPADL converter."""

from typing import Optional

from pandas import DataFrame

from socceraction.spadl import SPADLSchema

from . import config as spadlconfig

MGP_TO_SOCCERACTION_X = 1.05
MGP_TO_SOCCERACTION_Y = 0.68


class MyGamePlanEvent:
    """A class representing a MyGamePlan event."""

    pass


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
            start_x=event.coordinates[0] * MGP_TO_SOCCERACTION_X if event.coordinates else None,
            start_y=event.coordinates[1] * MGP_TO_SOCCERACTION_X if event.coordinates else None,
            **_get_end_location(event),
            **_parse_event(event),
        )
        actions.append(action)


def _get_end_location(event: MyGamePlanEvent) -> dict[str, Optional[float]]:
    if event.event_type == "pass":
        if event.get("pass"):
            return {
                "end_x": event.get("pass").end_coordinates[0] * MGP_TO_SOCCERACTION_X,
                "end_y": event.get("pass").end_coordinates[1] * MGP_TO_SOCCERACTION_Y,
            }
    elif event.event_type == "shot":
        if event.get("shot").get("shot_coordinate_y"):
            return {
                "end_x": 105,
                "end_y": event.get("shot").get("shot_coordinate_y") * MGP_TO_SOCCERACTION_Y,
            }
        else:
            return {
                "end_x": event.coordinates[0] * MGP_TO_SOCCERACTION_X
                if event.coordinates
                else None,
                "end_y": event.coordinates[1] * MGP_TO_SOCCERACTION_Y
                if event.coordinates
                else None,
            }
    elif event.event_type == "carry":
        if event.get("carry"):
            return {
                "end_x": event.get("carry").end_coordinates[0] * MGP_TO_SOCCERACTION_X,
                "end_y": event.get("carry").end_coordinates[1] * MGP_TO_SOCCERACTION_Y,
            }

    if event.coordinates:
        return {"end_x": event.coordinates[0], "end_y": event.coordinates[0]}
    return {"end_x": None, "end_y": None}


def _parse_event(event: MyGamePlanEvent) -> dict[str, int]:
    events = {
        "pass": _parse_pass_event,
    }
    parser = events.get(event.event_type, _parse_event_as_non_action)
    a, r, b = parser(event)
    return {
        "type_id": spadlconfig.actiontypes.index(a),
        "result_id": spadlconfig.results.index(r),
        "bodypart_id": spadlconfig.bodyparts.index(b),
    }


def _parse_pass_event(event: MyGamePlanEvent) -> tuple[str, str, str]:  # noqa: C901
    b = _parse_bodypart(event.get("pass", {}).get("body_part", None), default="foot")

    secondary_event_types = event.get("secondary_event_types", [])
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


def _parse_event_as_non_action(event: MyGamePlanEvent) -> tuple[str, str, str]:
    a = "non_action"
    r = "success"
    b = "foot"
    return a, r, b
