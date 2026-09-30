import pytest

from app.models import RubricCriterion
from app.services.scoring import anchoring_metrics, validate_scores, weighted_score

CRITERIA = [
    RubricCriterion(id=1, name="Problem", weight=20),
    RubricCriterion(id=2, name="Innovation", weight=25),
    RubricCriterion(id=3, name="Feasibility", weight=20),
    RubricCriterion(id=4, name="Impact", weight=20),
    RubricCriterion(id=5, name="Scalability", weight=15),
]


def test_weighted_score_0_to_100():
    scores = [{"criterion_id": i, "score": 10} for i in range(1, 6)]
    assert weighted_score(scores, CRITERIA, 10) == 100.0
    scores = [{"criterion_id": 1, "score": 5}, {"criterion_id": 2, "score": 8}, {"criterion_id": 3, "score": 6},
              {"criterion_id": 4, "score": 7}, {"criterion_id": 5, "score": 4}]
    assert weighted_score(scores, CRITERIA, 10) == pytest.approx(62.0)


def test_validate_requires_every_criterion():
    with pytest.raises(ValueError, match="missing"):
        validate_scores([{"criterion_id": 1, "score": 5}], CRITERIA, 10)
    with pytest.raises(ValueError, match="between"):
        validate_scores([{"criterion_id": i, "score": 11} for i in range(1, 6)], CRITERIA, 10)


@pytest.mark.parametrize(
    "initial, ai, revised, direction",
    [
        (70, 60, 70, "no_change"),
        (70, 60, 65, "toward_ai"),
        (70, 60, 75, "away_from_ai"),
        (50, 60, 55, "toward_ai"),
        (50, None, 55, "ai_unavailable"),
    ],
)
def test_anchoring_direction(initial, ai, revised, direction):
    m = anchoring_metrics(initial, ai, revised)
    assert m["revision_direction"] == direction
    assert m["initial_to_revised_difference"] == revised - initial
    if ai is not None:
        assert m["initial_to_ai_difference"] == ai - initial
