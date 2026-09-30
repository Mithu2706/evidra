"""Lexical signals used by the rule-based analyzer.

These rules are intentionally conservative and transparent: they locate
evidence and flag claims for human verification; they do not attempt to judge
quality beyond simple, explainable coverage measures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    title: re.Pattern[str]
    body: re.Pattern[str]


TOPICS: list[Topic] = [
    Topic("problem", "Problem definition", rx(r"problem|challenge|pain|context|why now"),
          rx(r"\b(problem|struggl\w*|cannot|can't|lack\w*|waste\w*|inefficien\w*|overcrowd\w*|crowded|expensive|delay\w*|rely on|only after|hard)\b")),
    Topic("target_users", "Target users", rx(r"who we serve|users|customers|audience|persona"),
          rx(r"\b(primary users?|target users?|secondary users?|target customers?|designed for|built for)\b")),
    Topic("solution", "Proposed solution", rx(r"solution|product|idea|overview|features"),
          rx(r"\b(we propose|our (app|platform|solution|product)|is an? (app|platform|tool|marketplace)|predicts|generates|shows|lets|helps|measures|alerts?)\b")),
    Topic("architecture", "Technical approach", rx(r"architecture|how it works|technology|tech stack|device|design|system"),
          rx(r"\b(model|api|sensors?|database|backend|pipeline|solver|algorithm|smart contracts?|hl7|fhir|lorawan|microcontroller|feature store)\b")),
    Topic("validation", "Validation & results", rx(r"validation|results|evidence|traction|field test|findings"),
          rx(r"\b(benchmark|study|tested|test set|held-out|retrospective|survey|interview\w*|measured|error|trial|field test|usability)\b")),
    Topic("impact", "Expected impact", rx(r"impact|benefit|outcome"),
          rx(r"\b(reduc\w+|sav(e|es|ing)|lower|fewer|improv\w+|remove|income|emissions?)\b")),
    Topic("market", "Market", rx(r"market|opportunity"), rx(r"\b(market|tam|sam|demand)\b")),
    Topic("business", "Business model", rx(r"business|revenue|pricing|unit cost|monetiz"),
          rx(r"\b(licen[cs]e|subscription|fee|pricing|priced|revenue|saas|per unit|target price)\b")),
    Topic("competition", "Existing alternatives", rx(r"competit|alternative|landscape|comparison"),
          rx(r"\b(competitors?|alternatives?|existing (solutions?|tools?|products?)|unlike|compared (to|with)|differentiat\w+)\b")),
    Topic("scalability", "Scaling plan", rx(r"scal|growth|expansion|rollout"),
          rx(r"\b(scale|scaling|citywide|regional|nationwide|expand\w*|rollout|network of \d+)\b")),
    Topic("plan", "Implementation plan", rx(r"plan|roadmap|timeline|next steps|deployment|milestone"),
          rx(r"\b(phase \d|q[1-4]\b|roadmap|milestone|will deploy|deploy\w*)\b")),
    Topic("team", "Team", rx(r"^team|about us|who we are|team$"),
          rx(r"\b(engineers?|developers?|scientists?|founders?|advisors?|nurse|researchers?)\b")),
]
TOPIC_BY_KEY = {t.key: t for t in TOPICS}

HIGHLIGHT_ORDER = [
    "problem", "target_users", "solution", "architecture", "validation", "impact",
    "business", "competition", "scalability", "plan",
]

# Criterion name/description → topics that count as evidence for it.
CRITERION_HINTS: list[tuple[re.Pattern[str], list[str]]] = [
    (rx(r"problem|need|pain|understand"), ["problem", "target_users"]),
    (rx(r"innovat|novel|original|creativ|unique|differentiat"), ["solution", "competition"]),
    (rx(r"technical|feasib|implement|architect|engineering|execution"), ["architecture", "validation", "plan"]),
    (rx(r"impact|benefit|social|environment|outcome"), ["impact", "validation"]),
    (rx(r"scal|growth|expan|rollout"), ["scalability", "business", "plan"]),
    (rx(r"business|market|commercial|viab|revenue|sustainab"), ["business", "market"]),
    (rx(r"team|capab"), ["team"]),
    (rx(r"user|design|ux|usab|experience"), ["target_users", "solution", "validation"]),
]

CLAIM_CATEGORY_TO_CRITERIA: dict[str, list[str]] = {
    "impact": ["impact"],
    "technical": ["architecture"],
    "business": ["business"],
    "market": ["business", "market", "scalability"],
    "novelty": ["solution", "competition"],
    "quantitative": ["impact"],
}

# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

QUANT_PATTERNS = [
    rx(r"\b\d+(\.\d+)?\s?%"),
    rx(r"[$€£]\s?\d"),
    rx(r"\b\d+(\.\d+)?\s?x\b|\b\d+ times (faster|cheaper|more|better)"),
    rx(r"\b(reduc\w*|cut\w*|sav\w*|increas\w*|improv\w*|lower\w*|remov\w*|eliminat\w*|doubl\w*|tripl\w*)\b[^.]{0,40}\b\d"),
    rx(r"\b\d[\d,.]*\s*(million|billion|thousand)?\s*(tonnes|tons|farms|users|customers|patients|students|households|villages|lives)\b"),
    rx(r"\b\d+\s*(years?|months?)\b[^.]{0,30}\b(battery|charge)|\b(battery|charge)\b[^.]{0,30}\b\d+\s*(years?|months?)"),
]
NOVELTY_PATTERN = rx(
    r"\b(world'?s first|first[- ]ever|the first (platform|solution|app|company|tool|marketplace|to)\b"
    r"|the only (platform|solution|app|tool)|revolutioni[sz]\w*|unprecedented|guarantee\w*|100% accurate)"
)
PLAN_PATTERN = rx(r"^(phase \d|q[1-4]\b|step \d|stage \d|year \d)|\b(will deploy|plan to|we plan|roadmap)\b")
TARGET_PATTERN = rx(r"^(goal|target|aim|objective)s?\b|\b(our goal|we aim)\b")
SUPPORT_PATTERN = rx(
    r"\b(survey\w*|interview\w*|study|studies|pilot results|measured|benchmark\w*|tested|test set|held-out|"
    r"retrospective|trial|experiment\w*|data from|according to|source:|report|n\s?=\s?\d|usability)\b"
)

PRICING_PATTERN = rx(r"\b(fee|target price|priced|pricing|subscription|licen[cs]e)\b")

CATEGORY_PATTERNS = [
    ("business", rx(r"\b(costs? \$|per unit|in parts)\b")),
    ("market", rx(r"\bmarket|revenue|customers|\$\s?\d+\s?(b|bn|billion|m|million)\b")),
    ("technical", rx(r"\b(battery|sensor|accuracy|latency|model|error|uptime)\b")),
    ("impact", rx(r"\b(reduc\w*|sav\w*|fewer|lower|remov\w*|emission\w*|co2|wait|cost\w*|income|onboard)\b")),
]

# ---------------------------------------------------------------------------
# Feasibility dependencies: (key, label, mention, explanation-if-present)
# ---------------------------------------------------------------------------

DEPENDENCIES: list[tuple[str, str, re.Pattern[str], re.Pattern[str], str]] = [
    (
        "hardware", "hardware",
        rx(r"\b(sensors?|devices?|hardware|buoy|modem|drones?|iot)\b"),
        rx(r"\b(unit cost|per unit|costs? \$|bill of materials|bom|prototype|datasheet|field test\w*|calibrat\w*)\b"),
        "The proposal depends on {what}, but hardware cost, specification or field validation is not explained.",
    ),
    (
        "ai_model", "AI/ML model",
        rx(r"\b(ai|machine learning|ml|model|algorithm)\b[^.]{0,50}\b(estimat\w*|predict\w*|detect\w*|classif\w*|recogni\w*|personali[sz]\w*|recommend\w*)|\b(uses? ai|ai[- ]powered|ai recommendations)\b"),
        rx(r"\b(accuracy|mean absolute error|error of|precision|recall|validated|benchmark\w*|test set|held-out|trained on)\b"),
        "The proposal relies on an AI/ML component ({what}), but no accuracy figures, training data or "
        "validation are described.",
    ),
    (
        "integration", "external integration",
        rx(r"\b(integrat\w+ with|partner (ngo|hospital|organi[sz]ation)|partner\b[^.]{0,20}\bwill|api access)\b"),
        rx(r"\b(agreements?|signed|letter of intent|loi|contract|confirmed|memorandum)\b"),
        "The plan depends on an external party ({what}); the submission does not state whether access or a "
        "partnership is confirmed.",
    ),
]

APPENDIX_PATTERN = rx(r"\b(appendix|annex|see attached|attached (document|file|sheet))\b")

COMMON_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (rx(r"route optimi[sz]\w*|routing solver|collection routes"), "sensor-driven collection route optimization"),
    (rx(r"marketplace"), "online marketplaces for this domain"),
    (rx(r"blockchain|token"), "blockchain-based credit or token platforms"),
    (rx(r"wait[- ]times?"), "wait-time forecasting and display tools"),
    (rx(r"study|tutor\w*|learning app|students"), "study-group and peer-learning apps"),
    (rx(r"water[- ]quality|sensor network"), "low-cost environmental sensor networks"),
    (rx(r"chatbot|assistant"), "AI chat assistants"),
]

TARGET_USER_PATTERN = rx(r"\b(primary users?|target users?|target customers?|designed for|built for)\b[:\s]")
DATA_PATTERN = rx(r"\d|survey|report|data|study|interview")
