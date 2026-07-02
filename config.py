MIN_VISIBLE_QUALITY = 60
SHOW_EXPIRED_SIGNALS = False
PIVOT_LEFT = 3
PIVOT_RIGHT = 2
# Distance Score preferuje zwarte dywergencje; zbyt długie układy są karane niższym wynikiem.
DISTANCE_PROFILE = {
    "1": (12, 24),
    "3": (11, 23),
    "5": (10, 22),
    "15": (8, 18),
    "30": (7, 16),
    "60": (6, 14),
    "240": (5, 12),
    "D": (4, 10)
}
