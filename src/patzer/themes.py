TACTICAL_THEMES: frozenset[str] = frozenset({
    "fork",
    "pin",
    "skewer",
    "hangingPiece",
    "backRankMate",
    "doubleCheck",
    "discoveredAttack",
})

STRATEGIC_THEMES: frozenset[str] = frozenset({
    "IQP_attack",
    "IQP_defence",
    "minority_attack",
    "pawn_storm",
    "outpost",
    "bishop_pair",
})

THEME_DESCRIPTIONS: dict[str, str] = {
    # Tactical
    "fork": "A piece attacks two or more enemy pieces simultaneously.",
    "pin": "A piece is pinned against a more valuable piece behind it, restricting its movement.",
    "skewer": "An attack on a valuable piece that, when it moves, exposes a less valuable piece behind it.",
    "hangingPiece": "An undefended piece that can be captured for free.",
    "backRankMate": "A checkmate delivered on the opponent's back rank, often exploiting a lack of escape squares.",
    "doubleCheck": "A move that puts the king in check from two pieces simultaneously.",
    "discoveredAttack": "Moving one piece reveals an attack from another piece behind it.",
    # Strategic
    "IQP_attack": "Attacking with the initiative that comes from an isolated queen's pawn, using piece activity and kingside pressure.",
    "IQP_defence": "Defending against an isolated queen's pawn by blockading it and trading pieces to reach a favourable endgame.",
    "minority_attack": "Advancing a minority of pawns to undermine and create weaknesses in the opponent's pawn majority.",
    "pawn_storm": "Advancing pawns aggressively toward the opponent's king to open lines for an attack.",
    "outpost": "Placing a piece on a square that cannot be attacked by enemy pawns, typically a knight on a strong central square.",
    "bishop_pair": "Exploiting the long-term advantage of two bishops vs bishop and knight or two knights in an open position.",
}
