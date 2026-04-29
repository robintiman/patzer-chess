// Main app. Composes game list + workspace + coach rail.
import { useState, useMemo, useEffect, useCallback, useRef, useLayoutEffect } from "react";
import { Chess } from "chess.js";
import { PATTERN_STATS, transformGameList, transformGameResponse, flattenPlies } from "./data";
import Board, { EvalBar } from "./Board";
import EvalGraph from "./EvalGraph";
import GameList from "./GameList";
import MoveList from "./MoveList";
import CoachPanel from "./Coach";
import TweaksPanel from "./Tweaks";

const DEFAULT_TWEAKS = {
  theme: "dark",
  tone: "socratic",
  engineReveal: "rich",
  coachPosition: "right",
  defaultBlind: true,
};

export default function App() {
  const [username, setUsernameState] = useState(() => localStorage.getItem("ggchess_username") || "");
  const [games, setGames] = useState(null);
  const [activeGameId, setActiveGameId] = useState(null);
  const [gameDetail, setGameDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState("");

  const [currentPly, setCurrentPly] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [blindMode, setBlindMode] = useState(true);
  const [annotations, setAnnotations] = useState({});
  const [tweakOpen, setTweakOpen] = useState(false);
  const [tweaks, setTweaksRaw] = useState(DEFAULT_TWEAKS);
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    document.body.className = `theme-${tweaks.theme}`;
  }, [tweaks.theme]);

  useEffect(() => { setBlindMode(tweaks.defaultBlind); }, [tweaks.defaultBlind]);

  function setTweaks(t) {
    setTweaksRaw(t);
    try { window.parent?.postMessage({ type: "__edit_mode_set_keys", edits: t }, "*"); } catch (_) {}
  }

  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === "__activate_edit_mode") { setEditMode(true); setTweakOpen(true); }
      if (e.data?.type === "__deactivate_edit_mode") { setEditMode(false); setTweakOpen(false); }
    };
    window.addEventListener("message", handler);
    window.parent?.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", handler);
  }, []);

  function setUsername(u) {
    localStorage.setItem("ggchess_username", u);
    setUsernameState(u);
    setGames(null);
    setActiveGameId(null);
    setGameDetail(null);
  }

  function syncAndLoadGames() {
    if (!username || syncing) return;
    setSyncing(true);
    setGames(null);
    fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    })
      .then((r) => {
        const reader = r.body.getReader();
        const drain = () => reader.read().then(({ done }) => { if (!done) drain(); });
        return drain();
      })
      .then(() => fetch(`/api/games?username=${encodeURIComponent(username)}`))
      .then((r) => r.json())
      .then((data) => {
        const transformed = transformGameList(data, username);
        setGames(transformed);
        if (transformed.length > 0) setActiveGameId(transformed[0].id);
      })
      .catch(() => setGames([]))
      .finally(() => setSyncing(false));
  }

  function startAnalysis() {
    if (!activeGameId || analysing) return;
    setAnalysing(true);
    setAnalysisStatus("Starting analysis…");

    fetch(`/api/analyse-game/${activeGameId}`, { method: "POST" })
      .then((r) => {
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        function pump() {
          return reader.read().then(({ done, value }) => {
            if (done) return;
            const text = dec.decode(value, { stream: true });
            for (const line of text.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const ev = JSON.parse(line.slice(6));
                if (ev.type === "status") setAnalysisStatus(ev.message);
                if (ev.type === "analyzing_move") setAnalysisStatus(`Analysing ${ev.san}…`);
                if (ev.type === "concept_identified") setAnalysisStatus(`Found ${ev.move_classification} on move ${ev.move_number}`);
                if (ev.type === "done") setAnalysisStatus(`Done — ${ev.error_count} errors found`);
                if (ev.type === "error") setAnalysisStatus(`Error: ${ev.message}`);
              } catch (_) {}
            }
            return pump();
          });
        }
        return pump();
      })
      .then(() => {
        // Reload game detail to get errors + eval graph
        setAnalysing(false);
        setDetailLoading(true);
        setGameDetail(null);
        return fetch(`/api/game/${activeGameId}`)
          .then((r) => r.json())
          .then((data) => {
            const g = transformGameResponse(data, username);
            g.dbId = activeGameId;
            const p = flattenPlies(g);
            const cp = p.map((x, i) => (x.isCritical ? i : -1)).filter((i) => i >= 0);
            setGameDetail({ game: g, plies: p, criticalPlies: cp });
            setCurrentPly(0);
            setAnnotations({});
            setDetailLoading(false);
          });
      })
      .catch((err) => {
        setAnalysisStatus(`Error: ${err.message}`);
        setAnalysing(false);
      });
  }

  // Sync on username set
  useEffect(() => {
    if (!username) return;
    syncAndLoadGames();
  }, [username]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch game detail when active game changes
  useEffect(() => {
    if (activeGameId == null) return;
    setDetailLoading(true);
    setGameDetail(null);
    fetch(`/api/game/${activeGameId}`)
      .then((r) => r.json())
      .then((data) => {
        const game = transformGameResponse(data, username);
        game.dbId = activeGameId;
        const plies = flattenPlies(game);
        const criticalPlies = plies.map((p, i) => (p.isCritical ? i : -1)).filter((i) => i >= 0);
        setGameDetail({ game, plies, criticalPlies });
        setCurrentPly(0);
        setAnnotations({});
        setDetailLoading(false);
      })
      .catch(() => setDetailLoading(false));
  }, [activeGameId]);

  if (!username) {
    return <SetupScreen onSetUsername={setUsername} tweaks={tweaks} />;
  }

  const game = gameDetail?.game ?? null;
  const plies = gameDetail?.plies ?? [];
  const criticalPlies = gameDetail?.criticalPlies ?? [];

  const [fens, lastMoves] = useMemo(() => {
    const chess = new Chess();
    const fens = [chess.fen()];
    const lastMoves = [null];
    for (let i = 1; i < plies.length; i++) {
      try {
        const move = chess.move(plies[i].san);
        lastMoves.push(move ? { from: move.from, to: move.to } : null);
      } catch (_) {
        lastMoves.push(null);
      }
      fens.push(chess.fen());
    }
    return [fens, lastMoves];
  }, [plies]);

  const fen = fens[currentPly] ?? "start";
  const plyInfo = plies[currentPly];

  const moveData = useMemo(() => {
    if (!game || !plyInfo) return null;
    const pair = game.moves.find((m) => m.n === plyInfo.moveNo);
    if (!pair) return null;
    return plyInfo.color === "w" ? pair.white : pair.black;
  }, [plyInfo, game]);

  const lastMove = lastMoves[currentPly] ?? null;

  const engineArrows = useMemo(() => {
    if (blindMode || !moveData?.isCritical) return [];
    const arrows = [];
    if (moveData.bestMoveUci) {
      arrows.push({ from: moveData.bestMoveUci.slice(0, 2), to: moveData.bestMoveUci.slice(2, 4), color: "accent" });
    }
    if (moveData.playerMoveUci && moveData.playerMoveUci !== moveData.bestMoveUci) {
      arrows.push({ from: moveData.playerMoveUci.slice(0, 2), to: moveData.playerMoveUci.slice(2, 4), color: "danger" });
    }
    return arrows;
  }, [blindMode, moveData]);

  const highlight = moveData?.isCritical ? moveData.square : null;
  const highlightKind = blindMode ? "critical" : "best";

  const workspaceRef = useRef(null);
  const [boardSize, setBoardSize] = useState(440);
  const [stackMoves, setStackMoves] = useState(false);

  useLayoutEffect(() => {
    const el = workspaceRef.current;
    if (!el) return;
    const update = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      const narrow = w < 720;
      setStackMoves(narrow);
      const sideReserved = narrow ? 0 : 220 + 16 + 200 + 16;
      const availW = w - 28 - 8 - 32 - sideReserved;
      const vReserved = 140 + 60 + 32 + (narrow ? 180 : 0);
      const availH = h - vReserved;
      setBoardSize(Math.max(280, Math.min(700, Math.min(availW, availH))) | 0);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const seek = useCallback((p) => {
    setCurrentPly(Math.max(0, Math.min(plies.length - 1, p)));
  }, [plies.length]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowLeft") seek(currentPly - 1);
      if (e.key === "ArrowRight") seek(currentPly + 1);
      if (e.key === "f" || e.key === "F") setFlipped((f) => !f);
      if (e.key === "b" || e.key === "B") setBlindMode((b) => !b);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [currentPly, seek]);

  function jumpCritical(delta) {
    if (!criticalPlies.length) return;
    const target = delta > 0
      ? criticalPlies.find((p) => p > currentPly) ?? criticalPlies[criticalPlies.length - 1]
      : [...criticalPlies].reverse().find((p) => p < currentPly) ?? criticalPlies[0];
    seek(target);
  }

  function updateAnnotation(ply, field, val) {
    setAnnotations((a) => ({ ...a, [ply]: { ...(a[ply] || {}), [field]: val } }));
  }

  const [triggerAsk, setTriggerAsk] = useState(null);

  // Tutorial mode — board takeover for interactive demonstrations
  const [tutorialMode, setTutorialMode] = useState(false);
  const [tutorialPlan, setTutorialPlan] = useState(null);
  const [tutorialStepIdx, setTutorialStepIdx] = useState(0);
  const [tutorialFen, setTutorialFen] = useState(null);
  const [awaitingUserMove, setAwaitingUserMove] = useState(false);
  const [tutorialFeedback, setTutorialFeedback] = useState(null);

  const startTutorial = useCallback((plan) => {
    setTutorialPlan(plan);
    setTutorialStepIdx(0);
    setTutorialFen(fens[currentPly] ?? new Chess().fen());
    setTutorialMode(true);
    setAwaitingUserMove(false);
    setTutorialFeedback(null);
  }, [fens, currentPly]);

  const exitTutorial = useCallback(() => {
    setTutorialMode(false);
    setTutorialPlan(null);
    setTutorialStepIdx(0);
    setTutorialFen(null);
    setAwaitingUserMove(false);
    setTutorialFeedback(null);
  }, []);

  const submitTutorialMove = useCallback((uciOrSan) => {
    if (!tutorialMode || !awaitingUserMove || !tutorialPlan) return;
    const step = tutorialPlan.steps[tutorialStepIdx];
    if (!step || step.type !== "question") return;

    // Normalize to UCI — SAN moves (containing letters like N/B/R/Q/K or short moves) get converted
    let uci = uciOrSan;
    if (uciOrSan.length < 4 || /[NBRQK]/.test(uciOrSan)) {
      try {
        const ch = new Chess(tutorialFen);
        const m = ch.move(uciOrSan);
        if (m) uci = m.from + m.to;
      } catch (_) {}
    }

    const isCorrect = uci.slice(0, 4) === (step.correct_uci || "").slice(0, 4);
    setAwaitingUserMove(false);

    if (isCorrect) {
      const ch = new Chess(tutorialFen);
      try { ch.move(step.correct_uci); setTutorialFen(ch.fen()); } catch (_) {}
      setTutorialFeedback({ correct: true, message: "Exactly right!" });
      setTimeout(() => { setTutorialFeedback(null); setTutorialStepIdx((i) => i + 1); }, 1500);
    } else {
      setTutorialFeedback({ correct: false, message: `Not quite — try ${step.correct_san}. ${step.hint || ""}` });
      setTimeout(() => { setAwaitingUserMove(true); setTutorialFeedback(null); }, 2500);
    }
  }, [tutorialMode, awaitingUserMove, tutorialPlan, tutorialStepIdx, tutorialFen]);

  // Animate "animate" steps
  useEffect(() => {
    if (!tutorialMode || !tutorialPlan) return;
    const steps = tutorialPlan.steps;
    if (tutorialStepIdx >= steps.length) return;
    const step = steps[tutorialStepIdx];
    if (step.type !== "animate") return;
    const t = setTimeout(() => {
      const ch = new Chess(tutorialFen);
      try { ch.move(step.uci); setTutorialFen(ch.fen()); } catch (_) {}
      setTutorialStepIdx((i) => i + 1);
    }, tutorialStepIdx === 0 ? 500 : 1200);
    return () => clearTimeout(t);
  }, [tutorialMode, tutorialStepIdx, tutorialPlan, tutorialFen]);

  // Activate board interaction on "question" steps
  useEffect(() => {
    if (!tutorialMode || !tutorialPlan) return;
    const step = tutorialPlan.steps[tutorialStepIdx];
    if (step?.type === "question") setAwaitingUserMove(true);
  }, [tutorialMode, tutorialStepIdx, tutorialPlan]);

  // Show summary message when all steps are done
  useEffect(() => {
    if (!tutorialMode || !tutorialPlan) return;
    if (tutorialStepIdx === tutorialPlan.steps.length && tutorialPlan.summary) {
      setTutorialFeedback({ correct: true, message: tutorialPlan.summary, isSummary: true });
    }
  }, [tutorialMode, tutorialStepIdx, tutorialPlan]);

  // Exit tutorial when user switches to a different game
  useEffect(() => { if (tutorialMode) exitTutorial(); }, [activeGameId]); // eslint-disable-line

  function handleAskCoach(ply) {
    seek(ply);
    const plyData = plies[ply];
    if (!plyData || !game) return;
    const pair = game.moves.find((m) => m.n === plyData.moveNo);
    const mData = plyData.color === "w" ? pair?.white : pair?.black;
    setTriggerAsk({
      question: `Tell me about ${plyData.moveNo}${plyData.color === "w" ? "." : "…"} ${plyData.san}`,
      fen: mData?.fenBefore || "",
      playerMoveUci: mData?.playerMoveUci || "",
      bestMoveUci: mData?.bestMoveUci || "",
      evalDrop: mData?.evalDrop || 0,
      conceptName: mData?.conceptName || "",
    });
  }

  return (
    <div className="app-root">
      <TopBar game={game} blindMode={blindMode} setBlindMode={setBlindMode}
        flipped={flipped} setFlipped={setFlipped}
        jumpCritical={jumpCritical} currentPly={currentPly} plies={plies} onSeek={seek}
        username={username} onChangeUser={() => setUsername("")} />

      <div className="app-body" data-layout={tweaks.coachPosition}>
        <aside className="col-games">
          <GameList games={games || []} activeId={activeGameId} onSelect={setActiveGameId}
            username={username} gamesLoading={games === null} onSync={syncAndLoadGames} syncing={syncing} />
          <PatternInsights />
        </aside>

        <main className="col-workspace" ref={workspaceRef}>
          {detailLoading ? (
            <div className="ws-loading">
              <div className="ws-spinner" />
              <span>Loading game…</span>
            </div>
          ) : game ? (
            <>
              <div className="ws-top">
                <GameTitleBar game={game} />
                {!game.analysed || analysing ? (
                  <AnalysisBanner analysing={analysing} status={analysisStatus} onStart={startAnalysis} />
                ) : (
                  <EvalGraph plies={plies} currentPly={currentPly} onSeek={seek}
                    criticalPlies={blindMode ? [] : criticalPlies} />
                )}
              </div>

              <div className="ws-main" data-stack={stackMoves}>
                <div className="ws-board-area">
                  <EvalBar evalCp={blindMode ? 0 : (plyInfo?.eval ?? 0)} height={boardSize} flipped={flipped} />
                  <div className="board-stack">
                    <Board
                      fen={tutorialMode ? tutorialFen : fen}
                      flipped={flipped}
                      size={boardSize}
                      lastMove={tutorialMode ? null : lastMove}
                      highlight={tutorialMode ? null : highlight}
                      highlightKind={highlightKind}
                      arrows={tutorialMode ? [] : engineArrows}
                      interactive={tutorialMode && awaitingUserMove}
                      onPieceDrop={tutorialMode && awaitingUserMove ? submitTutorialMove : null}
                    />
                    <BoardFooter plyInfo={plyInfo} currentPly={currentPly} total={plies.length - 1}
                      onSeek={seek} setFlipped={setFlipped} flipped={flipped} />
                  </div>
                </div>
                <div className="ws-moves-area">
                  <MoveList game={game} currentPly={currentPly} onSeek={seek} blindMode={blindMode}
                    userAnnotations={annotations} onUpdateAnnotation={updateAnnotation}
                    onAskCoach={handleAskCoach} />
                </div>
                <div className="ws-chat-area">
                  <CoachPanel currentPly={currentPly} plies={plies} game={game} moveData={moveData}
                    blindMode={blindMode} gameDbId={activeGameId}
                    triggerAsk={triggerAsk} onTriggerAskConsumed={() => setTriggerAsk(null)}
                    currentFen={fen}
                    playerRating={game?.youRating ?? null}
                    tutorialMode={tutorialMode}
                    tutorialFen={tutorialFen}
                    currentTutorialStep={tutorialMode && tutorialPlan ? (tutorialPlan.steps[tutorialStepIdx] ?? null) : null}
                    tutorialFeedback={tutorialFeedback}
                    onStartTutorial={startTutorial}
                    onExitTutorial={exitTutorial}
                    onSubmitTutorialMove={submitTutorialMove}
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="ws-empty">
              <div className="ws-empty-icon">◆</div>
              <div className="ws-empty-text">Select a game to begin your review</div>
            </div>
          )}
        </main>

      </div>

      <TweaksPanel open={tweakOpen} onClose={() => setTweakOpen(false)} tweaks={tweaks} setTweaks={setTweaks} />

      {!editMode && (
        <button className="fab-tweaks" onClick={() => setTweakOpen((o) => !o)} title="Tweaks">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </button>
      )}

      <style>{`
        .app-root { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        .app-body { flex: 1; display: grid; min-height: 0; overflow: hidden; }
        .app-body[data-layout="right"] { grid-template-columns: 260px minmax(0, 1fr); }
        @media (max-width: 1400px) { .app-body[data-layout="right"] { grid-template-columns: 220px minmax(0, 1fr); } }
        @media (max-width: 1200px) { .app-body[data-layout="right"] { grid-template-columns: 200px minmax(0, 1fr); } }
        @media (max-width: 1000px) { .app-body[data-layout="right"] { grid-template-columns: 180px minmax(0, 1fr); } }
        .app-body[data-layout="bottom"] { grid-template-columns: 280px 1fr; }
        .col-games { border-right: 1px solid var(--border); background: var(--bg-2); display: flex; flex-direction: column; overflow: hidden; }
        .col-workspace { display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
        .ws-top { padding: 14px 20px 10px; border-bottom: 1px solid var(--border); background: var(--bg-2); flex-shrink: 0; }
        .ws-main { flex: 1; display: grid; grid-template-columns: auto 220px 1fr; gap: 16px; padding: 16px; overflow: hidden; min-height: 0; align-items: stretch; }
        .ws-main[data-stack="true"] { grid-template-columns: 1fr; grid-auto-rows: auto; justify-items: center; }
        .ws-board-area { display: flex; gap: 8px; align-items: flex-start; align-self: start; }
        .board-stack { display: flex; flex-direction: column; gap: 10px; }
        .ws-moves-area { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }
        .ws-chat-area { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }
        .ws-loading { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--text-dim); font-size: 13px; }
        .ws-spinner { width: 24px; height: 24px; border: 2px solid var(--border-2); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .ws-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: var(--text-dim); }
        .ws-empty-icon { font-size: 28px; color: var(--border-2); }
        .ws-empty-text { font-size: 13px; font-family: var(--font-serif); font-style: italic; }
        .fab-tweaks { position: fixed; bottom: 18px; right: 18px; width: 38px; height: 38px; border-radius: 50%; background: var(--surface); border: 1px solid var(--border-2); color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow-2); z-index: 100; }
        .fab-tweaks:hover { color: var(--accent); border-color: var(--accent); }
      `}</style>
    </div>
  );
}

function SetupScreen({ onSetUsername, tweaks }) {
  const [input, setInput] = useState("");

  useEffect(() => {
    document.body.className = `theme-${tweaks?.theme || "dark"}`;
  }, [tweaks?.theme]);

  function submit() {
    const u = input.trim();
    if (u) onSetUsername(u);
  }

  return (
    <div className="setup-root">
      <div className="setup-card fade-up">
        <div className="setup-brand">
          <span className="setup-mark">◆</span>
          <span className="setup-name">gg-<span className="setup-accent">chess</span></span>
        </div>
        <p className="setup-sub">Enter your Chess.com username to load your games.</p>
        <div className="setup-row">
          <input className="setup-input" type="text" placeholder="Chess.com username"
            value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoFocus />
          <button className="setup-btn" onClick={submit} disabled={!input.trim()}>Start</button>
        </div>
      </div>
      <style>{`
        .setup-root { height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg); }
        .setup-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px 40px; min-width: 320px; max-width: 420px; display: flex; flex-direction: column; gap: 18px; box-shadow: var(--shadow-2); }
        .setup-brand { display: flex; align-items: center; gap: 8px; }
        .setup-mark { color: var(--accent); font-size: 18px; }
        .setup-name { font-family: var(--font-serif); font-size: 28px; font-style: italic; letter-spacing: -0.5px; color: var(--text); }
        .setup-accent { color: var(--accent); }
        .setup-sub { margin: 0; font-size: 13px; color: var(--text-muted); font-family: var(--font-serif); font-style: italic; }
        .setup-row { display: flex; gap: 8px; }
        .setup-input { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-family: var(--font-ui); font-size: 14px; padding: 10px 12px; outline: none; transition: border-color 0.15s; }
        .setup-input:focus { border-color: var(--accent); }
        .setup-btn { padding: 10px 18px; background: var(--accent); color: #0b0c0d; border: none; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; transition: filter 0.12s; }
        .setup-btn:hover:not(:disabled) { filter: brightness(1.08); }
        .setup-btn:disabled { opacity: 0.5; cursor: default; }
      `}</style>
    </div>
  );
}

function TopBar({ game, blindMode, setBlindMode, flipped, setFlipped, jumpCritical, currentPly, plies, onSeek, username, onChangeUser }) {
  return (
    <header className="top">
      <div className="top-brand">
        <span className="brand-mark">◆</span>
        <span className="brand-name">gg-<span className="brand-accent">chess</span></span>
      </div>
      <div className="top-center">
        <button className="top-arrow" onClick={() => jumpCritical(-1)} title="Previous critical moment">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <div className="top-breadcrumb">
          <span>Recent games</span>
          {game && (
            <>
              <span className="top-sep">/</span>
              <span className="top-cur">vs. {game.opponent}</span>
              <span className="top-cur-date">· {game.date}</span>
            </>
          )}
        </div>
        <button className="top-arrow" onClick={() => jumpCritical(1)} title="Next critical moment">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>
      <div className="top-actions">
        <button className="top-user" onClick={onChangeUser} title="Change user">
          {username}
        </button>
        <div className="blind-toggle" onClick={() => setBlindMode(!blindMode)} role="switch" aria-checked={blindMode} tabIndex="0">
          <span className={`bt-label ${blindMode ? "on" : ""}`}>Blind</span>
          <span className={`bt-track ${blindMode ? "on" : "off"}`}>
            <span className="bt-thumb" />
          </span>
          <span className={`bt-label ${!blindMode ? "on" : ""}`}>Engine</span>
        </div>
      </div>
      <style>{`
        .top { height: 56px; flex-shrink: 0; display: grid; grid-template-columns: 260px minmax(0, 1fr) 300px; align-items: center; padding: 0 16px 0 20px; background: var(--bg-2); border-bottom: 1px solid var(--border); gap: 16px; }
        .top-brand { display: flex; align-items: center; gap: 8px; }
        .brand-mark { color: var(--accent); font-size: 14px; }
        .brand-name { font-family: var(--font-serif); font-size: 22px; font-style: italic; letter-spacing: -0.5px; color: var(--text); white-space: nowrap; }
        .brand-accent { color: var(--accent); }
        .top-center { display: flex; align-items: center; justify-content: center; gap: 8px; }
        .top-arrow { width: 26px; height: 26px; background: none; border: 1px solid var(--border); border-radius: 99px; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.12s; }
        .top-arrow:hover { border-color: var(--warn); color: var(--warn); }
        .top-breadcrumb { display: flex; align-items: baseline; gap: 6px; font-size: 13px; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .top-sep { color: var(--text-dim); opacity: 0.5; }
        .top-cur { color: var(--text); font-weight: 500; }
        .top-cur-date { color: var(--text-dim); font-size: 12px; font-family: var(--font-mono); }
        .top-actions { display: flex; justify-content: flex-end; align-items: center; gap: 10px; }
        .top-user { background: none; border: 1px solid var(--border); border-radius: 99px; padding: 3px 10px; font-size: 12px; color: var(--text-muted); cursor: pointer; font-family: var(--font-mono); transition: all 0.12s; }
        .top-user:hover { color: var(--text); border-color: var(--border-2); }
        .blind-toggle { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; padding: 4px 8px; border-radius: 99px; background: var(--surface); border: 1px solid var(--border); }
        .blind-toggle:hover { border-color: var(--border-2); }
        .bt-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; font-family: var(--font-mono); transition: color 0.12s; }
        .bt-label.on { color: var(--text); }
        .bt-track { position: relative; width: 34px; height: 18px; background: var(--surface-3); border-radius: 99px; transition: background 0.18s; }
        .bt-track.on { background: var(--warn-muted); }
        .bt-track.off { background: var(--accent-muted); }
        .bt-thumb { position: absolute; top: 2px; width: 14px; height: 14px; border-radius: 50%; background: var(--text); transition: left 0.22s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.18s; }
        .bt-track.on .bt-thumb { left: 2px; background: var(--warn); }
        .bt-track.off .bt-thumb { left: 18px; background: var(--accent); }
      `}</style>
    </header>
  );
}

function GameTitleBar({ game }) {
  return (
    <div className="gtb">
      <div className="gtb-players">
        <PlayerBadge name={game.you} rating={game.youRating} color="white" isYou />
        <span className="gtb-vs">vs</span>
        <PlayerBadge name={game.opponent} rating={game.oppRating} color="black" />
      </div>
      <div className="gtb-meta">
        {game.opening !== "?" && (
          <span className="gtb-opening" title={game.opening}>
            {game.ecoCode !== "?" && <span className="gtb-eco">{game.ecoCode}</span>}
            {game.opening}
          </span>
        )}
        {game.opening !== "?" && <span className="gtb-sep">·</span>}
        <span>{game.timeControl}</span>
        <span className="gtb-sep">·</span>
        <span className={`gtb-result ${game.result === "0-1" ? "loss" : ""}`}>
          {game.result} {game.result === "0-1" ? "loss" : game.result === "1-0" ? "win" : "draw"}
        </span>
      </div>
      <style>{`
        .gtb { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 12px; flex-wrap: wrap; }
        .gtb-players { display: flex; align-items: center; gap: 10px; }
        .gtb-vs { font-family: var(--font-serif); font-style: italic; font-size: 14px; color: var(--text-dim); }
        .gtb-meta { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
        .gtb-sep { color: var(--text-dim); opacity: 0.5; }
        .gtb-opening { font-family: var(--font-serif); font-style: italic; font-size: 13px; color: var(--text-muted); }
        .gtb-eco { font-family: var(--font-mono); font-style: normal; font-size: 11px; color: var(--accent); background: var(--accent-muted); padding: 1px 5px; border-radius: 3px; margin-right: 4px; }
        .gtb-result { color: var(--text); font-weight: 600; }
        .gtb-result.loss { color: var(--danger); }
        .pb { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 99px; background: var(--surface); border: 1px solid var(--border); }
        .pb.you { border-color: var(--accent-dim); }
        .pb-dot { width: 8px; height: 8px; border-radius: 50%; border: 1px solid var(--border-2); }
        .pb-dot.white { background: #e8e6df; }
        .pb-dot.black { background: #2a2c2e; }
        .pb-name { font-size: 12px; font-weight: 500; color: var(--text); }
        .pb-rating { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
      `}</style>
    </div>
  );
}

function PlayerBadge({ name, rating, color, isYou }) {
  return (
    <div className={`pb ${isYou ? "you" : ""}`}>
      <span className={`pb-dot ${color}`} />
      <span className="pb-name">{name}</span>
      {rating && rating !== "?" && <span className="pb-rating">{rating}</span>}
    </div>
  );
}

function BoardFooter({ plyInfo, currentPly, total, onSeek, setFlipped, flipped }) {
  return (
    <div className="bf">
      <div className="bf-controls">
        <button onClick={() => onSeek(0)} disabled={currentPly === 0} title="Start">⏮</button>
        <button onClick={() => onSeek(currentPly - 1)} disabled={currentPly === 0} title="Previous">‹</button>
        <span className="bf-counter">{currentPly}/{total}</span>
        <button onClick={() => onSeek(currentPly + 1)} disabled={currentPly >= total} title="Next">›</button>
        <button onClick={() => onSeek(total)} disabled={currentPly >= total} title="End">⏭</button>
      </div>
      <div className="bf-move-label">
        {plyInfo?.san ? (
          <>
            <span className="bf-mn">{plyInfo.moveNo}{plyInfo.color === "w" ? "." : "…"}</span>
            <span className="bf-san">{plyInfo.san}</span>
            {plyInfo.clock && <span className="bf-clock">{plyInfo.clock}</span>}
          </>
        ) : (
          <span className="bf-mn">start</span>
        )}
      </div>
      <button className="bf-flip" onClick={() => setFlipped(!flipped)} title="Flip board (F)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polyline points="17 1 21 5 17 9"/>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
          <polyline points="7 23 3 19 7 15"/>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
        </svg>
      </button>
      <style>{`
        .bf { display: flex; align-items: center; gap: 14px; padding: 0 4px; }
        .bf-controls { display: flex; align-items: center; gap: 2px; }
        .bf-controls button { width: 30px; height: 28px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-muted); cursor: pointer; font-size: 13px; display: flex; align-items: center; justify-content: center; transition: all 0.12s; }
        .bf-controls button:hover:not(:disabled) { background: var(--surface-2); color: var(--text); }
        .bf-controls button:disabled { opacity: 0.3; cursor: default; }
        .bf-counter { font-family: var(--font-mono); font-size: 12px; color: var(--text-dim); min-width: 44px; text-align: center; }
        .bf-move-label { flex: 1; display: flex; align-items: baseline; gap: 6px; font-family: var(--font-mono); }
        .bf-mn { color: var(--text-dim); font-size: 13px; }
        .bf-san { color: var(--text); font-size: 15px; font-weight: 600; }
        .bf-clock { font-size: 11px; color: var(--text-dim); margin-left: auto; }
        .bf-flip { width: 30px; height: 28px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.12s; }
        .bf-flip:hover { color: var(--text); background: var(--surface-2); }
      `}</style>
    </div>
  );
}

function AnalysisBanner({ analysing, status, onStart }) {
  return (
    <div className="ab">
      {analysing ? (
        <>
          <div className="ab-spinner" />
          <span className="ab-status">{status || "Analysing…"}</span>
        </>
      ) : (
        <>
          <span className="ab-hint">Run Stockfish analysis to see the eval graph and find errors.</span>
          <button className="ab-btn" onClick={onStart}>Analyse game</button>
        </>
      )}
      <style>{`
        .ab { display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 4px; }
        .ab-spinner { width: 14px; height: 14px; border: 2px solid var(--border-2); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
        .ab-status { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ab-hint { font-size: 12px; color: var(--text-dim); font-family: var(--font-serif); font-style: italic; flex: 1; }
        .ab-btn { padding: 6px 14px; background: var(--accent); color: #0b0c0d; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; cursor: pointer; transition: filter 0.12s; flex-shrink: 0; }
        .ab-btn:hover { filter: brightness(1.08); }
      `}</style>
    </div>
  );
}

function PatternInsights() {
  return (
    <div className="pi">
      <div className="pi-head">
        <span className="pi-title">Patterns this month</span>
        <span className="pi-sub">Where I see you repeat yourself</span>
      </div>
      <div className="pi-list">
        {PATTERN_STATS.slice(0, 4).map((p, i) => (
          <div className={`pi-row sev-${p.severity}`} key={i}>
            <div className="pi-count">×{p.count}</div>
            <div className="pi-body">
              <div className="pi-tag">{p.tag}</div>
              <div className="pi-last">{p.lastSeen}</div>
            </div>
            <div className={`pi-trend trend-${p.trend}`}>
              {p.trend === "up" ? "↑" : p.trend === "down" ? "↓" : "·"}
            </div>
          </div>
        ))}
        {PATTERN_STATS.length === 0 && (
          <div className="pi-empty">Patterns appear after analysis</div>
        )}
      </div>
      <style>{`
        .pi { padding: 12px 16px 14px; border-top: 1px solid var(--border); flex-shrink: 0; }
        .pi-head { margin-bottom: 8px; }
        .pi-title { display: block; font-size: 11px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.6px; }
        .pi-sub { font-size: 11px; color: var(--text-muted); font-family: var(--font-serif); font-style: italic; }
        .pi-list { display: flex; flex-direction: column; gap: 4px; }
        .pi-empty { font-size: 12px; color: var(--text-dim); font-style: italic; font-family: var(--font-serif); padding: 6px 0; }
        .pi-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: var(--surface); border: 1px solid var(--border); border-left: 2px solid var(--text-dim); border-radius: var(--radius-sm); cursor: pointer; transition: border-color 0.12s; }
        .pi-row:hover { border-color: var(--border-2); }
        .pi-row.sev-high { border-left-color: var(--warn); }
        .pi-row.sev-med  { border-left-color: var(--info); }
        .pi-count { width: 28px; font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: var(--text); }
        .pi-body { flex: 1; min-width: 0; }
        .pi-tag { font-size: 12px; color: var(--text); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .pi-last { font-size: 10px; color: var(--text-dim); font-family: var(--font-mono); }
        .pi-trend { font-size: 14px; font-weight: 700; font-family: var(--font-mono); width: 16px; text-align: center; }
        .trend-up   { color: var(--warn); }
        .trend-down { color: var(--accent); }
        .trend-flat { color: var(--text-dim); }
      `}</style>
    </div>
  );
}
