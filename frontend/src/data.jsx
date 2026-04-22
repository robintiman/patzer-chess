// Utilities for transforming backend API responses into frontend UI shapes.
//
// Real data comes from:
//   GET /api/interesting-games?username=<user>  →  transformGameList()
//   GET /api/game/:id                           →  transformGameResponse()
//
// TODO: Add missing game list fields to backend:
//   - oppRating / youRating: parse WhiteElo/BlackElo headers from PGN
//   - opening / ecoCode: parse Opening/ECO headers from PGN
//   - ply: count half-moves and store on the games row
//
// TODO: GET /api/game/:id is missing:
//   - eval per move (every ply, not just errors): full Stockfish sweep needed
//   - class for non-error moves ("best", "good", "ok", "book"): not classified today
//   - clock: parse [%clk h:mm:ss] comments from PGN move text
//   - evalBefore / evalAfter: backend stores eval_drop_cp (relative) only
//   - bestLine as string[]: pv_san is stored as a space-joined string, split it
//   - brilliant classification: no heuristic in engine (sacrificial move + win% gain)
//
// TODO: POST /api/games/:id/review/judge — evaluate user-proposed SAN move with Stockfish,
//   return { verdict, note, evalAfter } — powers the Judge tab.
//
// TODO: GET /api/patterns?username=<user> — aggregate concept_name counts across positions.
//   Powers the PatternInsights sidebar.
//
// TODO: GET /api/drills?username=<user> — generate drill suggestions from recurring error patterns.
//
// TODO: Game sync UI — POST /api/sync { username, max_games }.

export function parsePgnHeaders(pgn) {
  const headers = {};
  const re = /\[(\w+)\s+"([^"]*)"\]/g;
  let m;
  while ((m = re.exec(pgn)) !== null) headers[m[1]] = m[2];
  return headers;
}

export function parsePgnMoves(pgn) {
  const body = pgn.replace(/\[[^\]]+\]\s*/g, "").trim();
  const clkRe = /\[%clk\s+(\d+:\d+:\d+(?:\.\d+)?)\]/;
  const moves = [];
  let i = 0;

  function skipWs() {
    while (i < body.length && /\s/.test(body[i])) i++;
  }

  function readComment() {
    i++;
    let s = "";
    while (i < body.length && body[i] !== "}") s += body[i++];
    i++;
    return s;
  }

  function skipVariation() {
    i++;
    let depth = 1;
    while (i < body.length && depth > 0) {
      if (body[i] === "(") depth++;
      else if (body[i] === ")") depth--;
      else if (body[i] === "{") readComment();
      i++;
    }
  }

  while (i < body.length) {
    skipWs();
    if (i >= body.length) break;
    if (body[i] === "{") { readComment(); continue; }
    if (body[i] === "(") { skipVariation(); continue; }

    let tok = "";
    while (i < body.length && !/[\s{}()]/.test(body[i])) tok += body[i++];
    if (!tok) continue;
    if (/^\d+\./.test(tok) || /^(1-0|0-1|1\/2-1\/2|\*)$/.test(tok) || /^\$\d+$/.test(tok)) continue;

    const san = tok.replace(/[!?]+$/, "").replace(/\$\d+$/, "");
    if (san.length < 2) continue;

    let clock = null;
    skipWs();
    if (i < body.length && body[i] === "{") {
      const comment = readComment();
      const cm = clkRe.exec(comment);
      if (cm) clock = cm[1];
    }
    moves.push({ san, clock });
  }
  return moves;
}

export function flattenPlies(game) {
  const plies = [{ san: null, ply: 0, moveNo: 0, color: null, eval: 0, class: "book" }];
  game.moves.forEach((m) => {
    if (m.white) plies.push({ ...m.white, moveNo: m.n, color: "w", ply: plies.length });
    if (m.black) plies.push({ ...m.black, moveNo: m.n, color: "b", ply: plies.length });
  });
  return plies;
}

export function transformGameResponse({ pgn, errors, move_evals, analysed }, username) {
  const headers = parsePgnHeaders(pgn);
  const moveList = parsePgnMoves(pgn);

  const white = headers.White || "?";
  const black = headers.Black || "?";
  const isWhite = username ? white.toLowerCase().includes(username.toLowerCase()) : true;

  // Index errors by (move_number, color) key; color derived from fen_before
  const errorMap = {};
  for (const e of errors || []) {
    const colorChar = (e.fen_before || "").split(" ")[1] || "w";
    errorMap[`${e.move_number}-${colorChar}`] = e;
  }

  // half_move_index is 1-based and matches idx+1 in the move list
  const evalByHalfMove = {};
  for (const ev of move_evals || []) {
    evalByHalfMove[ev.half_move_index] = ev.eval_cp;
  }

  const movePairs = [];
  for (let idx = 0; idx < moveList.length; idx++) {
    const moveNo = Math.floor(idx / 2) + 1;
    const color = idx % 2 === 0 ? "w" : "b";
    const { san, clock } = moveList[idx];
    const err = errorMap[`${moveNo}-${color}`];
    const halfMoveIdx = idx + 1;

    let moveData = { san, class: err?.move_classification || "ok", clock, eval: evalByHalfMove[halfMoveIdx] ?? 0 };

    if (err) {
      const pv = err.pv_san ? err.pv_san.split(" ").filter(Boolean) : [];
      moveData = {
        ...moveData,
        isCritical: true,
        moveNo,
        playerMoveUci: err.player_move || "",
        bestMoveUci: err.best_move || "",
        bestMove: pv[0] || err.best_move || "",
        bestLine: pv,
        evalDrop: err.eval_drop_cp || 0,
        evalBefore: null,
        evalAfter: null,
        conceptName: err.concept_name || "",
        conceptTag: err.concept_name || "",
        square: err.player_move ? err.player_move.slice(2, 4) : null,
        fenBefore: err.fen_before || "",
        coachSocratic: err.concept_explanation ? [err.concept_explanation] : [],
        comment: err.concept_explanation || "",
        coachJudge: { played: err.concept_explanation || "" },
        userAttempts: [],
      };
    }

    if (color === "w") {
      movePairs.push({ n: moveNo, white: moveData });
    } else {
      const last = movePairs[movePairs.length - 1];
      if (last && last.n === moveNo) last.black = moveData;
      else movePairs.push({ n: moveNo, black: moveData });
    }
  }

  const resultRaw = headers.Result || "?";

  return {
    dbId: null,
    analysed: !!analysed,
    you: isWhite ? white : black,
    opponent: isWhite ? black : white,
    youRating: isWhite ? (headers.WhiteElo || "?") : (headers.BlackElo || "?"),
    oppRating: isWhite ? (headers.BlackElo || "?") : (headers.WhiteElo || "?"),
    youColor: isWhite ? "white" : "black",
    result: resultRaw,
    date: headers.Date ? headers.Date.replace(/\./g, "-") : "?",
    timeControl: headers.TimeControl || "?",
    opening: headers.Opening || "?",
    ecoCode: headers.ECO || "?",
    moves: movePairs,
  };
}

export function transformGameList(apiGames, username) {
  return (apiGames || []).map((g) => {
    const r = g.result || "?";
    let result = "draw";
    if (r === "1-0") result = g.player_color === "white" ? "win" : "loss";
    else if (r === "0-1") result = g.player_color === "black" ? "win" : "loss";

    const phase =
      g.review_phase == null ? "unreviewed" :
      g.review_phase === "self_analysis" ? "in_progress" :
      g.review_phase === "comparison" ? "done" : "unreviewed";

    return {
      id: g.id,
      opponent: g.opponent || "?",
      oppRating: null,
      youRating: null,
      result,
      color: g.player_color,
      timeControl: g.time_control || "?",
      playedAt: g.played_at ? g.played_at.split(" ")[0] : "",
      ply: null,
      errorCount: g.error_count || 0,
      interest: g.interest_score || 0,
      opening: null,
      ecoCode: null,
      phase,
    };
  });
}

export const PATTERN_STATS = [];
export const DRILL_SUGGESTIONS = [];
