"""Implements the label tranformers of the VAEP framework."""

import pandas as pd  # type: ignore
from pandera.typing import DataFrame

import socceraction.spadl.config as spadl
from socceraction.spadl.schema import SPADLSchema


def scores(actions: DataFrame[SPADLSchema], nr_actions: int = 10) -> pd.DataFrame:
    """Determine whether the team possessing the ball scored a goal within the next x actions.

    Parameters
    ----------
    actions : pd.DataFrame
        The actions of a game.
    nr_actions : int, default=10  # noqa: DAR103
        Number of actions after the current action to consider.

    Returns
    -------
    pd.DataFrame
        A dataframe with a column 'scores' and a row for each action set to
        True if a goal was scored by the team possessing the ball within the
        next x actions; otherwise False.
    """
    # merging goals, owngoals and team_ids

    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )
    owngoals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("owngoal")
    )
    y = pd.concat([goals, owngoals, actions["team_id"]], axis=1)
    y.columns = ["goal", "owngoal", "team_id"]

    # adding future results
    for i in range(1, nr_actions):
        for c in ["team_id", "goal", "owngoal"]:
            shifted = y[c].shift(-i)
            shifted[-i:] = y[c].iloc[len(y) - 1]
            y["%s+%d" % (c, i)] = shifted

    res = y["goal"]
    for i in range(1, nr_actions):
        gi = y["goal+%d" % i] & (y["team_id+%d" % i] == y["team_id"])
        ogi = y["owngoal+%d" % i] & (y["team_id+%d" % i] != y["team_id"])
        res = res | gi | ogi

    return pd.DataFrame(res, columns=["scores"])


def concedes(actions: DataFrame[SPADLSchema], nr_actions: int = 10) -> pd.DataFrame:
    """Determine whether the team possessing the ball conceded a goal within the next x actions.

    Parameters
    ----------
    actions : pd.DataFrame
        The actions of a game.
    nr_actions : int, default=10  # noqa: DAR103
        Number of actions after the current action to consider.

    Returns
    -------
    pd.DataFrame
        A dataframe with a column 'concedes' and a row for each action set to
        True if a goal was conceded by the team possessing the ball within the
        next x actions; otherwise False.
    """
    # merging goals,owngoals and team_ids
    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )
    owngoals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("owngoal")
    )
    y = pd.concat([goals, owngoals, actions["team_id"]], axis=1)
    y.columns = ["goal", "owngoal", "team_id"]

    # adding future results
    for i in range(1, nr_actions):
        for c in ["team_id", "goal", "owngoal"]:
            shifted = y[c].shift(-i)
            shifted[-i:] = y[c].iloc[len(y) - 1]
            y["%s+%d" % (c, i)] = shifted

    res = y["owngoal"]
    for i in range(1, nr_actions):
        gi = y["goal+%d" % i] & (y["team_id+%d" % i] != y["team_id"])
        ogi = y["owngoal+%d" % i] & (y["team_id+%d" % i] == y["team_id"])
        res = res | gi | ogi

    return pd.DataFrame(res, columns=["concedes"])


def goal_from_shot(actions: DataFrame[SPADLSchema]) -> pd.DataFrame:
    """Determine whether a goal was scored from the current action.

    This label can be use to train an xG model.

    Parameters
    ----------
    actions : pd.DataFrame
        The actions of a game.

    Returns
    -------
    pd.DataFrame
        A dataframe with a column 'goal' and a row for each action set to
        True if a goal was scored from the current action; otherwise False.
    """
    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )

    return pd.DataFrame(goals, columns=["goal_from_shot"])


def scores_time_based_window(
    actions: DataFrame[SPADLSchema], nr_seconds: int = 15, nr_actions: int = 3
) -> pd.DataFrame:
    """Determine whether the team possessing the ball scored a goal within the next x seconds.

    Parameters
    ----------
    actions : pd.DataFrame
        The actions of a game.

    Returns
    -------
    pd.DataFrame
        A dataframe with a column 'scores' and a row for each action set to
        True if a goal was scored by the team possessing the ball within the
        next x seconds; otherwise False.
    """
    # merging avg_goals_data, owngoals and team_ids
    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )
    owngoals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("owngoal")
    )
    y = pd.concat([goals, owngoals, actions["team_id"]], axis=1)
    y.columns = ["goal", "owngoal", "team_id"]

    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )
    owngoals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("owngoal")
    )
    y = pd.concat([goals, owngoals, actions["team_id"]], axis=1)
    y.columns = ["goal", "owngoal", "team_id"]

    # adding future results
    for i in range(1, nr_actions):
        for c in ["team_id", "goal", "owngoal"]:
            shifted = y[c].shift(-i)
            shifted[-i:] = y[c].iloc[len(y) - 1]
            y["%s+%d" % (c, i)] = shifted

    res = y["goal"]
    for i in range(1, nr_actions):
        gi = y["goal+%d" % i] & (y["team_id+%d" % i] == y["team_id"])
        ogi = y["owngoal+%d" % i] & (y["team_id+%d" % i] != y["team_id"])
        res = res | gi | ogi
    for i in range(len(actions)):
        possession_team = actions["team_id"][i]
        start_time = actions["time_seconds"][i]
        j = i + 1

        # Search for subsequent actions
        # time restarts at 0 in every half, so by taking the absolute value,
        # you dont look at goals scored in the 2nd half (with a lower time in seconds)
        while j < len(actions) and abs(actions["time_seconds"][j] - start_time) < nr_seconds:
            if (
                y["goal"][j] and y["team_id"][j] == possession_team
            ):  # team possessing the ball scored a goal
                res.at[i] = True
                break
            elif (
                y["owngoal"][j] and y["team_id"][j] != possession_team
            ):  # other team conceded an owngoal
                res.at[i] = True
                break
            j += 1
    return pd.DataFrame(res, columns=["scores"])


def concedes_time_based_window(
    actions: DataFrame[SPADLSchema], nr_seconds: int = 15, nr_actions: int = 3
) -> pd.DataFrame:
    """Determine whether the team possessing the ball conceded a goal within the next x seconds.

    Parameters
    ----------
    actions : pd.DataFrame
        The actions of a game.

    Returns
    -------
    pd.DataFrame
        A dataframe with a column 'scores' and a row for each action set to
        True if a goal was conceded by the team possessing the ball within the
        next x seconds; otherwise False.
    """
    # merging goals,owngoals and team_ids
    goals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("success")
    )
    owngoals = actions["type_name"].str.contains("shot") & (
        actions["result_id"] == spadl.results.index("owngoal")
    )
    y = pd.concat([goals, owngoals, actions["team_id"]], axis=1)
    y.columns = ["goal", "owngoal", "team_id"]

    # adding future results
    for i in range(1, nr_actions):
        for c in ["team_id", "goal", "owngoal"]:
            shifted = y[c].shift(-i)
            shifted[-i:] = y[c].iloc[len(y) - 1]
            y["%s+%d" % (c, i)] = shifted

    res = y["owngoal"]
    for i in range(1, nr_actions):
        gi = y["goal+%d" % i] & (y["team_id+%d" % i] != y["team_id"])
        ogi = y["owngoal+%d" % i] & (y["team_id+%d" % i] == y["team_id"])
        res = res | gi | ogi

    for i in range(len(actions)):
        possession_team = actions["team_id"][i]
        start_time = actions["time_seconds"][i]
        j = i + 1

        # Search for subsequent actions in the same possession
        # time restarts at 0 in every half, so by taking the absolute value,
        # you dont look at goals scored in the 2nd half (with a lower time in seconds)
        while j < len(actions) and abs(actions["time_seconds"][j] - start_time) < nr_seconds:
            if y["goal"][j] and y["team_id"][j] != possession_team:  # other team scored a goal
                res.at[i] = True
                break
            elif (
                y["owngoal"][j] and y["team_id"][j] == possession_team
            ):  # team conceded an owngoal
                res.at[i] = True
                break
            j += 1
    return pd.DataFrame(res, columns=["concedes"])
