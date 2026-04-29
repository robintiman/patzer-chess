// Move list panel: shows all moves, grouped by move number.
// Highlights classifications and critical moments.

const CLASS_META = {
  brilliant:   { glyph: "!!", color: "#7ab9ff", label: "Brilliant" },
  best:        { glyph: "★",  color: "var(--accent)", label: "Best" },
  good:        { glyph: "",   color: "var(--text-muted)", label: "Good" },
  book:        { glyph: "",   color: "var(--text-dim)", label: "Book" },
  ok:          { glyph: "",   color: "var(--text-muted)", label: "Ok" },
  inaccuracy:  { glyph: "?!", color: "#dcb75a", label: "Inaccuracy" },
  mistake:     { glyph: "?",  color: "var(--warn)", label: "Mistake" },
  blunder:     { glyph: "??", color: "var(--danger)", label: "Blunder" },
};

function MoveList({ game, currentPly, onSeek, blindMode }) {
  // Build pairs from game.moves
  const pairs = game.moves;
  const listRef = React.useRef(null);

  // Scroll current into view
  React.useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector(`[data-ply="${currentPly}"]`);
    if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [currentPly]);

  function plyFor(moveNo, color) {
    // plies: index 1 = 1. white, 2 = 1...black, 3 = 2.white...
    return (moveNo - 1) * 2 + (color === "w" ? 1 : 2);
  }

  return (
    <div className="ml" ref={listRef}>
      {pairs.map((p) => (
        <div className="ml-row" key={p.n}>
          <span className="ml-num">{p.n}.</span>
          {p.white && (
            <MoveChip
              m={p.white}
              ply={plyFor(p.n, "w")}
              active={currentPly === plyFor(p.n, "w")}
              onClick={() => onSeek(plyFor(p.n, "w"))}
              blind={blindMode}
              youPlayed={true}
            />
          )}
          {p.black && (
            <MoveChip
              m={p.black}
              ply={plyFor(p.n, "b")}
              active={currentPly === plyFor(p.n, "b")}
              onClick={() => onSeek(plyFor(p.n, "b"))}
              blind={blindMode}
              youPlayed={false}
            />
          )}
        </div>
      ))}
      <style>{`
        .ml {
          display: grid;
          grid-template-columns: auto 1fr 1fr;
          gap: 2px 10px;
          padding: 10px 12px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          font-family: var(--font-mono);
          font-size: 13px;
          flex: 1;
          min-height: 0;
          overflow-y: auto;
          align-content: start;
        }
        .ml-row { display: contents; }
        .ml-num {
          color: var(--text-dim);
          font-weight: 500;
          padding: 3px 0;
          user-select: none;
          text-align: right;
          min-width: 28px;
        }
      `}</style>
    </div>
  );
}

function MoveChip({ m, active, onClick, blind, ply, youPlayed }) {
  const meta = CLASS_META[m.class] || CLASS_META.ok;
  // Hide error classifications in blind mode for user's own moves
  const showClass = !blind || !youPlayed;
  return (
    <button
      className={`mc ${active ? "active" : ""} ${showClass ? `cls-${m.class}` : ""} ${m.isCritical && !blind ? "critical" : ""}`}
      onClick={onClick}
      data-ply={ply}
    >
      <span className="mc-san">{m.san}</span>
      {showClass && meta.glyph && (
        <span className="mc-glyph" style={{ color: meta.color }}>{meta.glyph}</span>
      )}
      {m.isCritical && !blind && <span className="mc-dot" />}
      <style>{`
        .mc {
          display: inline-flex; align-items: center; gap: 3px;
          background: none; border: 1px solid transparent;
          border-radius: 3px;
          padding: 2px 6px;
          font: inherit; color: var(--text-muted);
          cursor: pointer; text-align: left;
          position: relative;
          transition: background 0.1s, color 0.1s;
        }
        .mc:hover { background: var(--surface-2); color: var(--text); }
        .mc.active {
          background: var(--accent);
          color: #0b0c0d !important;
          font-weight: 600;
        }
        .mc.active .mc-glyph { color: #0b0c0d !important; }
        .mc.cls-blunder     { color: var(--danger); }
        .mc.cls-mistake     { color: var(--warn); }
        .mc.cls-inaccuracy  { color: #dcb75a; }
        .mc.cls-brilliant   { color: #7ab9ff; font-weight: 600; }
        .mc.cls-best        { color: var(--accent); }
        .mc.critical { outline: 1px dashed var(--warn); outline-offset: -1px; }
        .mc-san { }
        .mc-glyph { font-size: 11px; }
        .mc-dot {
          position: absolute;
          top: -2px; right: -2px;
          width: 5px; height: 5px;
          background: var(--warn);
          border-radius: 50%;
          border: 1px solid var(--bg-2);
        }
      `}</style>
    </button>
  );
}

Object.assign(window, { MoveList, MoveChip, CLASS_META });
