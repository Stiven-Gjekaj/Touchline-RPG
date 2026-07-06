"""Central tuning constants for the game engine.

Everything here is a starting point for playtesting, not claimed to be perfectly
calibrated. Keeping them in one module makes the whole game trivially retunable.
"""

from __future__ import annotations

from touchline.engine.models import Position, TrainingFocus

#: Bumped whenever the persisted schema changes incompatibly. Saves whose stored
#: value differs are treated as incompatible rather than migrated.
SCHEMA_VERSION = 1

# --------------------------------------------------------------------------- #
# Ratings
# --------------------------------------------------------------------------- #

#: Per-position attribute weights (each row sums to 1.0). Used both to compute
#: ``Player.overall()`` and to skew generated attributes toward a position.
POSITION_WEIGHTS: dict[Position, dict[str, float]] = {
    Position.GK: {"pace": 0.05, "shooting": 0.00, "passing": 0.15,
                  "defending": 0.10, "physical": 0.20, "goalkeeping": 0.50},
    Position.DF: {"pace": 0.15, "shooting": 0.05, "passing": 0.15,
                  "defending": 0.40, "physical": 0.25, "goalkeeping": 0.00},
    Position.MF: {"pace": 0.15, "shooting": 0.15, "passing": 0.35,
                  "defending": 0.20, "physical": 0.15, "goalkeeping": 0.00},
    Position.FW: {"pace": 0.30, "shooting": 0.35, "passing": 0.15,
                  "defending": 0.05, "physical": 0.15, "goalkeeping": 0.00},
}

#: The single attribute a position most exercises during a match (drives
#: match-minutes growth and NPC training choices).
PRIMARY_ATTRIBUTE: dict[Position, str] = {
    Position.GK: "goalkeeping",
    Position.DF: "defending",
    Position.MF: "passing",
    Position.FW: "shooting",
}

# --------------------------------------------------------------------------- #
# World / league structure
# --------------------------------------------------------------------------- #

NUM_TIERS = 3
CLUBS_PER_TIER = 12
#: Clubs promoted/relegated between adjacent tiers each season. Symmetric so
#: every division keeps a constant club count.
PROMOTION_RELEGATION_SLOTS = 3

# --------------------------------------------------------------------------- #
# Player generation
# --------------------------------------------------------------------------- #

#: Mean overall by tier, and the spread (std dev) of players within a tier.
TIER_MEAN_OVERALL: dict[int, int] = {1: 70, 2: 58, 3: 46}
TIER_SPREAD = 8

CLUB_OFFSET_STD = 4.0          # per-club deviation from its tier mean
CLUB_OFFSET_CLAMP = 10.0
ATTRIBUTE_JITTER_STD = 6.0     # per-attribute noise around the position skew
TARGET_OVERALL_MIN = 20
TARGET_OVERALL_MAX = 95

SQUAD_SIZE = 20
MIN_SQUAD_SIZE = 18            # below this at season end triggers a youth intake
#: Rough positional make-up of a generated squad (sums to SQUAD_SIZE).
SQUAD_POSITION_COUNTS: dict[Position, int] = {
    Position.GK: 3,
    Position.DF: 7,
    Position.MF: 7,
    Position.FW: 3,
}

PLAYER_AGE_MEAN = 25.0
PLAYER_AGE_STD = 4.0
PLAYER_AGE_MIN = 16
PLAYER_AGE_MAX = 38

YOUNG_POTENTIAL_MIN_BONUS = 5   # age < 21 potential headroom above target
YOUNG_POTENTIAL_MAX_BONUS = 25
YOUNG_AGE_CEILING = 21          # "young" for potential-headroom purposes
VETERAN_AGE_FLOOR = 29          # at/above this, potential ~= current overall

# The user's created player: a young unknown with room to grow.
USER_START_AGE_MIN = 16
USER_START_AGE_MAX = 18
USER_START_OVERALL_MIN = 40
USER_START_OVERALL_MAX = 50

# --------------------------------------------------------------------------- #
# Match simulation
# --------------------------------------------------------------------------- #

BASE_XG = 1.35                 # baseline expected goals per side in an even match
XG_SCALE_FACTOR = 40.0         # rating-point gap that shifts xG by ~1.0
HOME_ADVANTAGE = 4.0           # rating points added to the home side
MIN_XG = 0.15                  # floor so even a huge mismatch keeps some chance

ASSIST_PROBABILITY = 0.65      # chance a given goal has an assist at all

# Personal-rating tuning (user's player).
RATING_BASE = 6.0
RATING_PER_GOAL = 0.8
RATING_PER_ASSIST = 0.5
RATING_RESULT_SWING = 0.3      # +/- for a big win / big loss
RATING_NOISE_STD = 0.4
BIG_MARGIN = 3                 # goal margin considered a "big" win/loss

INJURY_BASE_CHANCE = 0.03      # per match, before physical/condition adjustment
YELLOW_CARD_CHANCE = 0.10
RED_CARD_CHANCE = 0.01

# --------------------------------------------------------------------------- #
# Season calendar (30-week cycle)
# --------------------------------------------------------------------------- #

SEASON_LENGTH = 30
PRESEASON_END = 3              # weeks 1-3: training only, window open
REGULAR_SEASON_START = 4       # weeks 4-25: 22 match weeks
REGULAR_SEASON_END = 25
SEASON_END_WEEK = 26           # standings finalised, promotion/relegation, etc.
OFFSEASON_START = 27           # weeks 27-30: training, primary transfer window
MATCH_WEEKS = REGULAR_SEASON_END - REGULAR_SEASON_START + 1  # 22

# --------------------------------------------------------------------------- #
# Progression / retirement
# --------------------------------------------------------------------------- #

DECLINE_START_AGE = 30
RETIREMENT_MIN_AGE = 33
RETIREMENT_HARD_CAP_AGE = 41
USER_FORCED_RETIRE_OVERALL = 30   # forced only if also past USER_FORCED_RETIRE_AGE
USER_FORCED_RETIRE_AGE = 35
USER_DECLINE_WARNING_AGE = 33

CONDITION_MATCH_DROP = 18      # condition lost after playing a match
CONDITION_TRAINING_REGEN = 12  # condition recovered in a training/off week
CONDITION_REST_REGEN = 25      # extra recovery when the focus is REST

#: Attributes each training focus can improve.
ATTRS_BOOSTED_BY: dict[TrainingFocus, tuple[str, ...]] = {
    TrainingFocus.ATTACKING: ("shooting", "pace"),
    TrainingFocus.PLAYMAKING: ("passing", "shooting"),
    TrainingFocus.DEFENSIVE: ("defending", "physical"),
    TrainingFocus.PHYSICAL: ("physical", "pace"),
    TrainingFocus.BALANCED: ("pace", "shooting", "passing", "defending",
                             "physical", "goalkeeping"),
    TrainingFocus.REST: (),
}

#: Default training focus an NPC of each position picks.
NPC_FOCUS_BY_POSITION: dict[Position, TrainingFocus] = {
    Position.GK: TrainingFocus.BALANCED,     # the only focus that grows goalkeeping
    Position.DF: TrainingFocus.DEFENSIVE,
    Position.MF: TrainingFocus.PLAYMAKING,
    Position.FW: TrainingFocus.ATTACKING,
}

# Attribute growth tuning.
TRAINING_GAIN_CHOICES = (1, 1, 2)        # weighted toward +1 per successful roll
MATCH_MINUTES_GROWTH_SCALE = 0.25         # playing grows slower than dedicated training
YOUNG_AGE_FACTOR = 1.5                     # age <= 21
PRIME_AGE_FACTOR = 1.0                     # age 22-25
FADING_AGE_FACTOR = 0.5                    # age 26-29

#: Attributes decline fastest first (legs before game-reading).
DECLINE_WEIGHTS: dict[str, float] = {
    "pace": 1.5, "physical": 1.3, "shooting": 1.0,
    "defending": 0.8, "passing": 0.7, "goalkeeping": 0.8,
}
DECLINE_PER_YEAR = 0.05                    # decline chance grows 5%/yr past 30
DECLINE_CHANCE_CAP = 0.6

# Youth intake (squad replenishment at season end).
YOUTH_INTAKE_AGE_MIN = 17
YOUTH_INTAKE_AGE_MAX = 20
