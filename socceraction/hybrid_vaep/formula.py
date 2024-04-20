"""Implements the formula of the Hybrid-VAEP framework."""
import pandas as pd  # type: ignore
from pandera.typing import DataFrame, Series

from socceraction.spadl.schema import SPADLSchema


def _prev(x: pd.Series) -> pd.Series:
    prev_x = x.shift(1)
    prev_x[:1] = x.values[0]
    return prev_x


_samephase_nb: int = 10


def offensive_value(
    actions: DataFrame[SPADLSchema],
    scores_standard: Series[float],
    scores_resultfree: Series[float],
    concedes_resultfree: Series[float],
) -> Series[float]:
    r"""Compute the offensive value of each action.

    Hybrid-VAEP defines the *offensive value* of an action as the change in scoring
    probability before and after the action.

    .. math::

      \Delta P_{score}(a_{i}, t) = P^{k}_{score}(S_i, t) - P^{k}_{score_resultfree}(S_{i-1}, t)

    where :math:`P_{score}(S_i, t)` is the probability that team :math:`t`
    which possesses the ball in state :math:`S_i` will score in the next 10
    actions (considering the result)
    and :math:`P_{score}(S_i, t)` is the probability that team :math:`t`
    which possesses the ball in state :math:`S_i` will score in the next 10
    actions (not considering the result).

    Parameters
    ----------
    actions : pd.DataFrame
        SPADL action.
    scores_standard : pd.Series
        The probability of scoring from each corresponding game state,
        estimated byb a model considering the result of the action.
    scores_resultfree : pd.Series
        The probability of scoring from each corresponding game state,
        estimated by a model not considering the result of the action.
    concedes_resultfree : pd.Series
        The probability of conceding from each corresponding game state,
        estimated by a model not considering the result of the action.

    Returns
    -------
    pd.Series
        The offensive value of each action.
    """
    sameteam = _prev(actions.team_id) == actions.team_id
    prev_scores_resultfree = _prev(scores_resultfree) * sameteam + _prev(concedes_resultfree) * (
        ~sameteam
    )

    # if the previous action was too long ago, the odds of scoring are now 0
    toolong_idx = abs(actions.time_seconds - _prev(actions.time_seconds)) > _samephase_nb
    prev_scores_resultfree[toolong_idx] = 0.0

    # if the previous action was a goal, the odds of scoring are now 0
    prevgoal_idx = (_prev(actions.type_name).isin(['shot', 'shot_freekick', 'shot_penalty'])) & (
        _prev(actions.result_name) == 'success'
    )
    prev_scores_resultfree[prevgoal_idx] = 0.0
    prev_scores_resultfree = prev_scores_resultfree.astype(float)

    # fixed odds of scoring when penalty
    penalty_idx = actions.type_name == 'shot_penalty'
    prev_scores_resultfree[penalty_idx] = 0.792453

    # fixed odds of scoring when corner
    corner_idx = actions.type_name.isin(['corner_crossed', 'corner_short'])
    prev_scores_resultfree[corner_idx] = 0.046500

    return scores_standard - prev_scores_resultfree


def defensive_value(
    actions: DataFrame[SPADLSchema],
    scores_resultfree: Series[float],
    concedes_standard: Series[float],
    concedes_resultfree: Series[float],
) -> Series[float]:
    r"""Compute the defensive value of each action.

    VAEP defines the *defensive value* of an action as the change in conceding
    probability.

    .. math::

      \Delta P_{concede}(a_{i}, t) = P^{k}_{concede}(S_i, t) - P^{k}_{concede}(S_{i-1}, t)

    where :math:`P_{concede}(S_i, t)` is the probability that team :math:`t`
    which possesses the ball in state :math:`S_i` will concede in the next 10
    actions (considering the result)
    and :math:`P_{concede_resultfree}(S_i, t)` is the probability that team :math:`t`
    which possesses the ball in state :math:`S_i` will concede in the next 10
    actions (not considering the result)

    Parameters
    ----------
    actions : pd.DataFrame
        SPADL action.
    scores_resultfree : pd.Series
        The probability of scoring from each corresponding game state,
        estimated by a model not considering the result of the action.
    concedes_standard : pd.Series
        The probability of conceding from each corresponding game state,
        estimated by a model considering the result of the action.
    concedes_resultfree : pd.Series
        The probability of conceding from each corresponding game state,
        estimated by a model not considering the result of the action.

    Returns
    -------
    pd.Series
        The defensive value of each action.
    """
    sameteam = _prev(actions.team_id) == actions.team_id
    prev_concedes_resultfree = _prev(concedes_resultfree) * sameteam + _prev(scores_resultfree) * (
        ~sameteam
    )

    toolong_idx = abs(actions.time_seconds - _prev(actions.time_seconds)) > _samephase_nb
    prev_concedes_resultfree[toolong_idx] = 0

    # if the previous action was a goal, the odds of conceding are now 0
    prevgoal_idx = (_prev(actions.type_name).isin(['shot', 'shot_freekick', 'shot_penalty'])) & (
        _prev(actions.result_name) == 'success'
    )
    prev_concedes_resultfree[prevgoal_idx] = 0

    return -(concedes_standard - prev_concedes_resultfree)


def value(
    actions: DataFrame[SPADLSchema],
    Pscores_standard: Series[float],
    Pscores_resultfree: Series[float],
    Pconcedes_standard: Series[float],
    Pconcedes_resultfree: Series[float],
) -> pd.DataFrame:
    r"""Compute the offensive, defensive and VAEP value of each action.

    The total VAEP value of an action is the difference between that action's
    offensive value and defensive value.

    .. math::

      V_{VAEP}(a_i) = \Delta P_{score}(a_{i}, t) - \Delta P_{concede}(a_{i}, t)

    Parameters
    ----------
    actions : pd.DataFrame
        SPADL action.
    Pscores_standard : pd.Series
        The probability of scoring from each corresponding game state, estimated by a model considering the result
    Pscores_resultfree : pd.Series
        The probability of scoring from each corresponding game state, estimated by a model not considering the result
    Pconcedes_standard : pd.Series
        The probability of conceding from each corresponding game state, estimated by a model considering the result
    Pconcedes_resultfree : pd.Series
        The probability of conceding from each corresponding game state, estimated by a model not considering the result

    Returns
    -------
    pd.DataFrame
        The 'offensive_value', 'defensive_value' and 'vaep_value' of each action.

    See Also
    --------
    :func:`~socceraction.hybrid-vaep.formula.offensive_value`: The offensive value
    :func:`~socceraction.hybrid-vaep.formula.defensive_value`: The defensive value
    """
    v = pd.DataFrame()
    v['offensive_value'] = offensive_value(
        actions, Pscores_standard, Pscores_resultfree, Pconcedes_resultfree
    )
    v['defensive_value'] = defensive_value(
        actions, Pscores_resultfree, Pconcedes_standard, Pconcedes_resultfree
    )
    v['vaep_value'] = v['offensive_value'] + v['defensive_value']
    return v
