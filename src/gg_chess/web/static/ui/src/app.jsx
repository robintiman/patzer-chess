// Main app. Composes game list + workspace + coach rail.

const { useState, useMemo, useEffect, useCallback } = React;

const DEFAULT_TWEAKS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "tone": "socratic",
  "engineReveal": "rich",
  "coachPosition": "right",
  "defaultBlind": true
}/*EDITMODE-END*/;

function App() {
  // Core state
  const [activeGameId, setActiveGameId] = useState(null);
  const [currentPly, setCurrentPly] = useState(31);
  const [flipped, setFlipped] = useState(false);
  const [lastFlippedForGame, setLastFlippedForGame] = useState(null);
  const [blindMode, setBlindMode] = useState(true);
  const [annotations, setAnnotations] = useState({}); // {ply: {thought, classification}}
  const [proposedArrow, setProposedArrow] = useState(null); // {from, to, color}
  const [tweakOpen, setTweakOpen] = useState(false);
  const [tweaks, setTweaksRaw] = useState(DEFAULT_TWEAKS);
  const [editMode, setEditMode] = useState(false);

  // Apply theme
  useEffect(() => {
    document.body.className = `theme-${tweaks.theme}`;
  }, [tweaks.theme]);

  // Default blind respected when switching
  useEffect(() => { setBlindMode(tweaks.defaultBlind); }, [tweaks.defaultBlind]);

  function setTweaks(t) {
    setTweaksRaw(t);
    try {
      window.parent?.postMessage({ type: "__edit_mode_set_keys", edits: t }, "*");
    } catch (e) {}
  }

  // Edit mode host protocol
  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === "__activate_edit_mode") { setEditMode(true); setTweakOpen(true); }
      if (e.data?.type === "__deactivate_edit_mode") { setEditMode(false); setTweakOpen(false); }
    };
    window.addEventListener("message", handler);
    window.parent?.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", handler);
  }, []);

  const [username, setUsername] = useState(() => localStorage.getItem("gg_username") || "");
  const [games, setGames] = useState([]);
  const [syncing, setSyncing] = useState(false);

  function changeUsername(u) {
    setUsername(u);
    localStorage.setItem("gg_username", u);
  }

  async function fetchGames(user) {
    if (!user) return;
    try {
      const res = await fetch(`/api/games?username=${encodeURIComponent(user)}`);
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        const mapped = data.map(g => {
          const isWhite = g.player_color === "white";
          const result = g.result === "1-0" ? (isWhite ? "win" : "loss")
                       : g.result === "0-1" ? (isWhite ? "loss" : "win")
                       : "draw";
          return {
            id: g.id,
            opponent: g.opponent || "?",
            oppRating: null,
            youRating: null,
            result,
            color: g.player_color,
            timeControl: g.time_control || "",
            playedAt: (g.played_at || "").split(" ")[0],
            ply: 0,
            errorCount: g.error_count || 0,
            interest: 0.5,
            opening: "",
            phase: "unreviewed",
          };
        });
        setGames(mapped);
        setActiveGameId(prev => prev === null ? mapped[0].id : prev);
      }
    } catch (e) {
      console.error("fetchGames failed", e);
    }
  }

  async function handleSync() {
    if (!username || syncing) return;
    setSyncing(true);
    try {
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const ev = JSON.parse(line.slice(6));
          if (ev.type === "done") fetchGames(username);
        }
      }
    } catch (e) {
      console.error("sync failed", e);
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => { fetchGames(username); }, [username]);

  // Auto-flip to match player color whenever the active game changes.
  // Using render-phase state update so the flip is applied immediately
  // with no intermediate render showing the wrong orientation.
  const activeGame = games.find(g => g.id === activeGameId) ?? null;
  if (activeGame && activeGame.id !== lastFlippedForGame) {
    setLastFlippedForGame(activeGame.id);
    setFlipped(activeGame.color === "black");
  }

  const game = FOCAL_GAME;
  const plies = FOCAL_PLIES;

  const board = useMemo(() => boardAtPly(plies, currentPly), [currentPly, plies]);

  const plyInfo = plies[currentPly];
  // For the prototype, critical moment metadata lives on the WHITE half of pair {n=16,21,28}.
  const moveData = useMemo(() => {
    const moveNo = plyInfo?.moveNo;
    const color = plyInfo?.color;
    const pair = game.moves.find((m) => m.n === moveNo);
    if (!pair) return null;
    const half = color === "w" ? pair.white : pair.black;
    return half?.isCritical ? half : half;
  }, [plyInfo, game]);

  const prevMoveSq = useMemo(() => {
    if (currentPly <= 0) return null;
    const p = plies[currentPly];
    if (!p?.san) return null;
    const dest = sanDest(p.san);
    return dest;
  }, [currentPly, plies]);

  const lastMove = useMemo(() => {
    const dest = prevMoveSq;
    return dest ? { to: dest } : null;
  }, [prevMoveSq]);

  // Engine arrows only when not blind AND critical move
  const engineArrows = useMemo(() => {
    if (blindMode) return [];
    const arrows = [];
    if (moveData?.isCritical && moveData?.bestMove) {
      // arrow for best
      const bm = moveData.bestMove;
      const bmClean = bm.replace(/[+#]/g, "");
      const dest = sanDest(bmClean);
      // Approximate: derive from a heuristic map
      const knownFroms = {
        "Qxg6": { from: "h5", to: "g6" },
        "Re1":  { from: "e4", to: "e1" },
        "Nf5":  { from: "g3", to: "f5" },
      };
      const k = knownFroms[bmClean];
      if (k) arrows.push({ ...k, color: "accent" });
      if (moveData.playerMove) {
        const pm = moveData.playerMove;
        const knownFromsPlayer = {
          "Nxf7": { from: "g5", to: "f7" },
          "Nd2":  { from: "f3", to: "d2" },
          "Qd4":  { from: "h4", to: "d4" },
        };
        const kp = knownFromsPlayer[pm];
        if (kp) arrows.push({ ...kp, color: "danger" });
      }
    }
    return arrows;
  }, [blindMode, moveData]);

  const allArrows = proposedArrow ? [...engineArrows, proposedArrow] : engineArrows;

  // Highlight critical square
  const highlight = !blindMode && moveData?.isCritical ? moveData.square
                   : blindMode && moveData?.isCritical ? moveData.square
                   : null;
  const highlightKind = blindMode ? "critical" : "best";

  // Responsive board size based on the workspace column
  const workspaceRef = React.useRef(null);
  const [boardSize, setBoardSize] = React.useState(440);
  const [stackMoves, setStackMoves] = React.useState(false);
  React.useLayoutEffect(() => {
    const el = workspaceRef.current;
    if (!el) return;
    const update = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      const narrow = w < 720;
      setStackMoves(narrow);
      // Width budget: eval bar(28) + gap(8) + padding(32) + (moves: 220 if side-by-side, else 0)
      const sideReserved = narrow ? 0 : 160 + 16;
      const availW = w - 28 - 8 - 32 - sideReserved;
      // Height budget: top bar ~140, footer ~60, padding 32, moves(160 if stacked)
      const vReserved = 140 + 60 + 32 + (narrow ? 180 : 0);
      const availH = h - vReserved;
      const s = Math.max(280, Math.min(680, Math.min(availW, availH)));
      setBoardSize(Math.floor(s));
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Navigation
  const seek = useCallback((p) => {
    const clamped = Math.max(0, Math.min(plies.length - 1, p));
    setCurrentPly(clamped);
    setProposedArrow(null);
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
    const list = CRITICAL_PLIES;
    if (!list.length) return;
    const current = list.findIndex((p) => p >= currentPly);
    let target;
    if (delta > 0) {
      target = list.find((p) => p > currentPly) ?? list[list.length - 1];
    } else {
      target = [...list].reverse().find((p) => p < currentPly) ?? list[0];
    }
    seek(target);
  }

  function onProposeMove(att) {
    // Show arrow for the proposed move
    const pm = att.move;
    const fromMap = {
      "Qxg6": { from: "h5", to: "g6" },
      "Qxh6": { from: "h5", to: "h6" },
      "Rxh6": { from: "h4", to: "h6" },
      "Re1":  { from: "e4", to: "e1" },
      "Re3":  { from: "e4", to: "e3" },
    };
    const arrow = fromMap[pm];
    if (arrow) setProposedArrow({ ...arrow, color: att.verdict === "best" ? "accent" : att.verdict === "close" ? "warn" : "danger" });
  }

  function updateAnnotation(ply, field, val) {
    setAnnotations((a) => ({ ...a, [ply]: { ...(a[ply] || {}), [field]: val } }));
  }

  return (
    <div className="app-root">
      <TopBar
        game={game}
        blindMode={blindMode}
        setBlindMode={setBlindMode}
        flipped={flipped} setFlipped={setFlipped}
        jumpCritical={jumpCritical}
        currentPly={currentPly}
        plies={plies}
        onSeek={seek}
      />

      <div className="app-body" data-layout={tweaks.coachPosition}>
        <aside className="col-games">
          <GameList games={games} activeId={activeGameId} onSelect={setActiveGameId}
                    username={username} onUsernameChange={changeUsername}
                    onSync={handleSync} syncing={syncing} />
          <PatternInsights />
        </aside>

        <main className="col-workspace" ref={workspaceRef}>
          <div className="ws-top">
            <GameTitleBar game={game} blindMode={blindMode} />
            <EvalGraph
              plies={plies}
              currentPly={currentPly}
              onSeek={seek}
              criticalPlies={blindMode ? [] : CRITICAL_PLIES}
            />
          </div>

          <div className="ws-main" data-stack={stackMoves}>
            <div className="ws-board-area">
              <EvalBar
                evalCp={blindMode ? 0 : (plyInfo?.eval ?? 0)}
                height={boardSize}
                flipped={flipped}
              />
              <div className="board-stack">
                <Board
                  board={board}
                  flipped={flipped}
                  size={boardSize}
                  lastMove={lastMove}
                  highlight={highlight}
                  highlightKind={highlightKind}
                  arrows={allArrows}
                  annotations={[]}
                />
                <BoardFooter
                  plyInfo={plyInfo}
                  currentPly={currentPly}
                  total={plies.length - 1}
                  onSeek={seek}
                  setFlipped={setFlipped}
                  flipped={flipped}
                />
              </div>
            </div>

            <div className="ws-moves-area">
              <MoveList game={game} currentPly={currentPly} onSeek={seek} blindMode={blindMode} />
            </div>
          </div>
        </main>

        <aside className="col-coach">
          <CoachPanel
            currentPly={currentPly}
            plies={plies}
            game={game}
            moveData={moveData}
            onRequestSquare={() => {}}
            onRequestArrow={setProposedArrow}
            blindMode={blindMode}
            onProposeMove={onProposeMove}
            userAnnotations={annotations}
            onUpdateAnnotation={updateAnnotation}
            onOpenVariation={() => {}}
          />
        </aside>
      </div>

      <TweaksPanel open={tweakOpen} onClose={() => setTweakOpen(false)} tweaks={tweaks} setTweaks={setTweaks} />

      {!editMode && (
        <button className="fab-tweaks" onClick={() => setTweakOpen((o) => !o)} title="Tweaks">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
      )}

      <style>{`
        .app-root {
          display: flex; flex-direction: column;
          height: 100vh;
          overflow: hidden;
        }
        .app-body {
          flex: 1;
          display: grid;
          min-height: 0;
          overflow: hidden;
        }
        .app-body[data-layout="right"] {
          grid-template-columns: 260px minmax(0, 1fr) 360px;
        }
        @media (max-width: 1400px) {
          .app-body[data-layout="right"] {
            grid-template-columns: 220px minmax(0, 1fr) 320px;
          }
        }
        @media (max-width: 1200px) {
          .app-body[data-layout="right"] {
            grid-template-columns: 200px minmax(0, 1fr) 300px;
          }
        }
        @media (max-width: 1000px) {
          .app-body[data-layout="right"] {
            grid-template-columns: 180px minmax(0, 1fr) 280px;
          }
        }
        .app-body[data-layout="bottom"] {
          grid-template-columns: 280px 1fr;
          grid-template-rows: 1fr 280px;
        }
        .app-body[data-layout="bottom"] .col-coach {
          grid-column: 1 / -1;
          border-left: none;
          border-top: 1px solid var(--border);
          max-height: 280px;
        }
        .col-games {
          border-right: 1px solid var(--border);
          background: var(--bg-2);
          display: flex; flex-direction: column;
          overflow: hidden;
        }
        .col-workspace {
          display: flex; flex-direction: column;
          overflow: hidden;
          min-width: 0;
        }
        .col-coach {
          min-width: 0;
          overflow: hidden;
        }
        .ws-top {
          padding: 14px 20px 10px;
          border-bottom: 1px solid var(--border);
          background: var(--bg-2);
          flex-shrink: 0;
        }
        .ws-main {
          flex: 1;
          display: grid;
          grid-template-columns: auto 160px;
          gap: 16px;
          padding: 16px;
          overflow: auto;
          min-height: 0;
          align-items: stretch;
        }
        .ws-main[data-stack="true"] {
          grid-template-columns: 1fr;
          grid-auto-rows: auto;
          justify-items: center;
        }
        .ws-board-area {
          display: flex;
          gap: 8px;
          align-items: flex-start;
        }
        .board-stack {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .ws-moves-area {
          display: flex;
          flex-direction: column;
          min-width: 0;
          min-height: 0;
          overflow: hidden;
        }
        .fab-tweaks {
          position: fixed;
          bottom: 18px; right: 18px;
          width: 38px; height: 38px;
          border-radius: 50%;
          background: var(--surface);
          border: 1px solid var(--border-2);
          color: var(--text-muted);
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          box-shadow: var(--shadow-2);
          z-index: 100;
        }
        .fab-tweaks:hover { color: var(--accent); border-color: var(--accent); }
      `}</style>
    </div>
  );
}

function TopBar({ game, blindMode, setBlindMode, flipped, setFlipped, jumpCritical, currentPly, plies, onSeek }) {
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
          <span className="top-sep">/</span>
          <span className="top-cur">vs. {game.opponent}</span>
          <span className="top-cur-date">· {game.date}</span>
        </div>
        <button className="top-arrow" onClick={() => jumpCritical(1)} title="Next critical moment">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>

      <div className="top-actions">
        <div className="blind-toggle" onClick={() => setBlindMode(!blindMode)} role="switch" aria-checked={blindMode} tabIndex="0">
          <span className={`bt-label ${blindMode ? "on" : ""}`}>Blind</span>
          <span className={`bt-track ${blindMode ? "on" : "off"}`}>
            <span className="bt-thumb" />
          </span>
          <span className={`bt-label ${!blindMode ? "on" : ""}`}>Engine</span>
        </div>
      </div>

      <style>{`
        .top {
          height: 56px;
          flex-shrink: 0;
          display: grid;
          grid-template-columns: 260px minmax(0, 1fr) 260px;
          align-items: center;
          padding: 0 16px 0 20px;
          background: var(--bg-2);
          border-bottom: 1px solid var(--border);
          gap: 16px;
        }
        .top-brand {
          display: flex; align-items: center; gap: 8px;
        }
        .brand-mark {
          color: var(--accent);
          font-size: 14px;
        }
        .brand-name {
          font-family: var(--font-serif);
          font-size: 22px;
          font-style: italic;
          letter-spacing: -0.5px;
          color: var(--text);
          white-space: nowrap;
        }
        .brand-accent {
          color: var(--accent);
        }
        .top-center {
          display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .top-arrow {
          width: 26px; height: 26px;
          background: none;
          border: 1px solid var(--border);
          border-radius: 99px;
          color: var(--text-muted);
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.12s;
        }
        .top-arrow:hover {
          border-color: var(--warn);
          color: var(--warn);
        }
        .top-breadcrumb {
          display: flex; align-items: baseline; gap: 6px;
          font-size: 13px;
          color: var(--text-dim);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .top-sep { color: var(--text-dim); opacity: 0.5; }
        .top-cur { color: var(--text); font-weight: 500; }
        .top-cur-date { color: var(--text-dim); font-size: 12px; font-family: var(--font-mono); }
        .top-actions {
          display: flex; justify-content: flex-end; align-items: center; gap: 12px;
        }
        .blind-toggle {
          display: inline-flex; align-items: center; gap: 8px;
          cursor: pointer;
          user-select: none;
          padding: 4px 8px;
          border-radius: 99px;
          background: var(--surface);
          border: 1px solid var(--border);
        }
        .blind-toggle:hover { border-color: var(--border-2); }
        .bt-label {
          font-size: 11px;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.6px;
          font-weight: 600;
          font-family: var(--font-mono);
          transition: color 0.12s;
        }
        .bt-label.on { color: var(--text); }
        .bt-track {
          position: relative;
          width: 34px; height: 18px;
          background: var(--surface-3);
          border-radius: 99px;
          transition: background 0.18s;
        }
        .bt-track.on { background: var(--warn-muted); }
        .bt-track.off { background: var(--accent-muted); }
        .bt-thumb {
          position: absolute;
          top: 2px;
          width: 14px; height: 14px;
          border-radius: 50%;
          background: var(--text);
          transition: left 0.22s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.18s;
        }
        .bt-track.on .bt-thumb { left: 2px; background: var(--warn); }
        .bt-track.off .bt-thumb { left: 18px; background: var(--accent); }
      `}</style>
    </header>
  );
}

function GameTitleBar({ game, blindMode }) {
  return (
    <div className="gtb">
      <div className="gtb-players">
        <PlayerBadge name={game.you} rating={game.youRating} color="white" isYou />
        <span className="gtb-vs">vs</span>
        <PlayerBadge name={game.opponent} rating={game.oppRating} color="black" />
      </div>
      <div className="gtb-meta">
        <span className="gtb-opening" title={game.opening}>
          <span className="gtb-eco">{game.ecoCode}</span> {game.opening}
        </span>
        <span className="gtb-sep">·</span>
        <span>{game.timeControl}</span>
        <span className="gtb-sep">·</span>
        <span className={`gtb-result ${game.result === "0-1" ? "loss" : ""}`}>
          {game.result} {game.result === "0-1" ? "loss" : game.result === "1-0" ? "win" : "draw"}
        </span>
      </div>
      <style>{`
        .gtb {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 10px;
          gap: 12px;
          flex-wrap: wrap;
        }
        .gtb-players {
          display: flex; align-items: center; gap: 10px;
        }
        .gtb-vs {
          font-family: var(--font-serif);
          font-style: italic;
          font-size: 14px;
          color: var(--text-dim);
        }
        .gtb-meta {
          display: flex; align-items: center; gap: 6px;
          font-size: 12px;
          color: var(--text-muted);
          font-family: var(--font-mono);
        }
        .gtb-sep { color: var(--text-dim); opacity: 0.5; }
        .gtb-opening {
          font-family: var(--font-serif);
          font-style: italic;
          font-size: 13px;
          color: var(--text-muted);
        }
        .gtb-eco {
          font-family: var(--font-mono);
          font-style: normal;
          font-size: 11px;
          color: var(--accent);
          background: var(--accent-muted);
          padding: 1px 5px;
          border-radius: 3px;
          margin-right: 4px;
        }
        .gtb-result {
          color: var(--text);
          font-weight: 600;
        }
        .gtb-result.loss { color: var(--danger); }
      `}</style>
    </div>
  );
}

function PlayerBadge({ name, rating, color, isYou }) {
  return (
    <div className={`pb ${isYou ? "you" : ""}`}>
      <span className={`pb-dot ${color}`} />
      <span className="pb-name">{name}</span>
      <span className="pb-rating">{rating}</span>
      <style>{`
        .pb {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 4px 10px;
          border-radius: 99px;
          background: var(--surface);
          border: 1px solid var(--border);
        }
        .pb.you { border-color: var(--accent-dim); }
        .pb-dot {
          width: 8px; height: 8px; border-radius: 50%;
          border: 1px solid var(--border-2);
        }
        .pb-dot.white { background: #e8e6df; }
        .pb-dot.black { background: #2a2c2e; }
        .pb-name {
          font-size: 12px; font-weight: 500;
          color: var(--text);
        }
        .pb-rating {
          font-family: var(--font-mono);
          font-size: 11px;
          color: var(--text-muted);
        }
      `}</style>
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
        {plyInfo?.san && (
          <>
            <span className="bf-mn">{plyInfo.moveNo}{plyInfo.color === "w" ? "." : "…"}</span>
            <span className="bf-san">{plyInfo.san}</span>
            {plyInfo.clock && <span className="bf-clock">{plyInfo.clock}</span>}
          </>
        )}
        {!plyInfo?.san && <span className="bf-mn">start</span>}
      </div>
      <button className="bf-flip" onClick={() => setFlipped(!flipped)} title="Flip board (F)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
      </button>
      <style>{`
        .bf {
          display: flex; align-items: center; gap: 14px;
          padding: 0 4px;
        }
        .bf-controls {
          display: flex; align-items: center; gap: 2px;
        }
        .bf-controls button {
          width: 30px; height: 28px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          color: var(--text-muted);
          cursor: pointer;
          font-size: 13px;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.12s;
        }
        .bf-controls button:hover:not(:disabled) {
          background: var(--surface-2);
          color: var(--text);
        }
        .bf-controls button:disabled { opacity: 0.3; cursor: default; }
        .bf-counter {
          font-family: var(--font-mono);
          font-size: 12px;
          color: var(--text-dim);
          min-width: 44px;
          text-align: center;
        }
        .bf-move-label {
          flex: 1;
          display: flex; align-items: baseline; gap: 6px;
          font-family: var(--font-mono);
        }
        .bf-mn { color: var(--text-dim); font-size: 13px; }
        .bf-san { color: var(--text); font-size: 15px; font-weight: 600; }
        .bf-clock {
          font-size: 11px;
          color: var(--text-dim);
          margin-left: auto;
        }
        .bf-flip {
          width: 30px; height: 28px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          color: var(--text-muted);
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.12s;
        }
        .bf-flip:hover { color: var(--text); background: var(--surface-2); }
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
      </div>
      <style>{`
        .pi {
          padding: 12px 16px 14px;
          border-top: 1px solid var(--border);
          flex-shrink: 0;
        }
        .pi-head { margin-bottom: 8px; }
        .pi-title {
          display: block;
          font-size: 11px; font-weight: 600;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.6px;
        }
        .pi-sub {
          font-size: 11px;
          color: var(--text-muted);
          font-family: var(--font-serif);
          font-style: italic;
        }
        .pi-list { display: flex; flex-direction: column; gap: 4px; }
        .pi-row {
          display: flex; align-items: center; gap: 8px;
          padding: 6px 8px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-left: 2px solid var(--text-dim);
          border-radius: var(--radius-sm);
          cursor: pointer;
          transition: border-color 0.12s;
        }
        .pi-row:hover { border-color: var(--border-2); }
        .pi-row.sev-high { border-left-color: var(--warn); }
        .pi-row.sev-med  { border-left-color: var(--info); }
        .pi-count {
          width: 28px;
          font-family: var(--font-mono);
          font-size: 12px;
          font-weight: 600;
          color: var(--text);
        }
        .pi-body { flex: 1; min-width: 0; }
        .pi-tag {
          font-size: 12px;
          color: var(--text);
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .pi-last {
          font-size: 10px;
          color: var(--text-dim);
          font-family: var(--font-mono);
        }
        .pi-trend {
          font-size: 14px;
          font-weight: 700;
          font-family: var(--font-mono);
          width: 16px;
          text-align: center;
        }
        .trend-up   { color: var(--warn); }
        .trend-down { color: var(--accent); }
        .trend-flat { color: var(--text-dim); }
      `}</style>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("app")).render(<App />);
