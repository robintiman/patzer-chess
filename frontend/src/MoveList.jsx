import { useRef, useEffect, useState } from "react";
import { createPortal } from "react-dom";

export const CLASS_META = {
  brilliant:  { glyph: "!!", color: "#7ab9ff", label: "Brilliant" },
  best:       { glyph: "★",  color: "var(--accent)", label: "Best" },
  good:       { glyph: "",   color: "var(--text-muted)", label: "Good" },
  book:       { glyph: "",   color: "var(--text-dim)", label: "Book" },
  ok:         { glyph: "",   color: "var(--text-muted)", label: "Ok" },
  inaccuracy: { glyph: "?!", color: "#dcb75a", label: "Inaccuracy" },
  mistake:    { glyph: "?",  color: "var(--warn)", label: "Mistake" },
  blunder:    { glyph: "??", color: "var(--danger)", label: "Blunder" },
};

const ANNOTATION_OPTIONS = [
  { v: "brilliant" },
  { v: "good" },
  { v: "inaccuracy" },
  { v: "mistake" },
  { v: "blunder" },
];

export default function MoveList({ game, currentPly, onSeek, blindMode, userAnnotations, onUpdateAnnotation, onAskCoach }) {
  const pairs = game.moves;
  const listRef = useRef(null);
  const [ctxMenu, setCtxMenu] = useState(null); // { ply, x, y, m }
  const [noteState, setNoteState] = useState(null); // { ply, x, y }

  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector(`[data-ply="${currentPly}"]`);
    if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [currentPly]);

  useEffect(() => {
    if (!ctxMenu) return;
    const onDown = (e) => { if (!e.target.closest(".ml-ctx")) setCtxMenu(null); };
    const onKey = (e) => { if (e.key === "Escape") setCtxMenu(null); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [!!ctxMenu]);

  useEffect(() => {
    if (!noteState) return;
    const onDown = (e) => { if (!e.target.closest(".ml-note-pop")) setNoteState(null); };
    const onKey = (e) => { if (e.key === "Escape") setNoteState(null); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [!!noteState]);

  function plyFor(moveNo, color) {
    return (moveNo - 1) * 2 + (color === "w" ? 1 : 2);
  }

  function openCtxMenu(e, ply, m) {
    e.preventDefault();
    const menuW = 220;
    const menuH = 280;
    const x = e.clientX + menuW > window.innerWidth ? window.innerWidth - menuW - 8 : e.clientX;
    const y = e.clientY + menuH > window.innerHeight ? window.innerHeight - menuH - 8 : e.clientY;
    setCtxMenu({ ply, x, y, m });
    setNoteState(null);
  }

  function handleClassify(ply, val) {
    const current = userAnnotations?.[ply]?.classification;
    onUpdateAnnotation?.(ply, "classification", current === val ? null : val);
    setCtxMenu(null);
  }

  function handleAskCoach(ply) {
    setCtxMenu(null);
    onAskCoach?.(ply);
  }

  function handleAddNote(ply) {
    const { x, y } = ctxMenu;
    setCtxMenu(null);
    setNoteState({ ply, x, y });
  }

  return (
    <div className="ml" ref={listRef}>
      {pairs.map((p) => (
        <div className="ml-row" key={p.n}>
          <span className="ml-num">{p.n}.</span>
          {p.white && (() => {
            const ply = plyFor(p.n, "w");
            return (
              <MoveChip
                m={p.white} ply={ply}
                active={currentPly === ply}
                onClick={() => onSeek(ply)}
                onContextMenu={(e) => openCtxMenu(e, ply, p.white)}
                blind={blindMode}
                userAnnotation={userAnnotations?.[ply]}
              />
            );
          })()}
          {p.black && (() => {
            const ply = plyFor(p.n, "b");
            return (
              <MoveChip
                m={p.black} ply={ply}
                active={currentPly === ply}
                onClick={() => onSeek(ply)}
                onContextMenu={(e) => openCtxMenu(e, ply, p.black)}
                blind={blindMode}
                userAnnotation={userAnnotations?.[ply]}
              />
            );
          })()}
        </div>
      ))}

      {ctxMenu && createPortal(
        <MoveContextMenu
          ply={ctxMenu.ply}
          m={ctxMenu.m}
          x={ctxMenu.x}
          y={ctxMenu.y}
          blindMode={blindMode}
          userAnnotation={userAnnotations?.[ctxMenu.ply]}
          onClassify={(val) => handleClassify(ctxMenu.ply, val)}
          onAskCoach={() => handleAskCoach(ctxMenu.ply)}
          onAddNote={() => handleAddNote(ctxMenu.ply)}
        />,
        document.body
      )}

      {noteState && createPortal(
        <NotePopover
          x={noteState.x}
          y={noteState.y}
          value={userAnnotations?.[noteState.ply]?.thought || ""}
          onChange={(val) => onUpdateAnnotation?.(noteState.ply, "thought", val)}
          onClose={() => setNoteState(null)}
        />,
        document.body
      )}

      <style>{`
        .ml {
          display: grid; grid-template-columns: auto 1fr 1fr;
          gap: 2px 10px; padding: 10px 12px;
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); font-family: var(--font-mono); font-size: 13px;
          max-height: 100%; overflow-y: auto; align-content: start;
        }
        .ml-row { display: contents; }
        .ml-num { color: var(--text-dim); font-weight: 500; padding: 3px 0; user-select: none; text-align: right; min-width: 28px; }
      `}</style>
    </div>
  );
}

function MoveContextMenu({ ply, m, x, y, blindMode, userAnnotation, onClassify, onAskCoach, onAddNote }) {
  const engineMeta = CLASS_META[m?.class];
  const userClass = userAnnotation?.classification;
  const moveNo = Math.ceil(ply / 2);
  const color = ply % 2 === 1 ? "w" : "b";

  return (
    <div className="ml-ctx" style={{ left: x, top: y }}>
      <div className="ctx-head">
        <span className="ctx-move">{moveNo}{color === "w" ? "." : "…"} {m?.san}</span>
        {!blindMode && engineMeta?.label && (
          <span className="ctx-engine-verdict" style={{ color: engineMeta.color }}>
            Engine: {engineMeta.label}{engineMeta.glyph ? ` ${engineMeta.glyph}` : ""}
          </span>
        )}
      </div>
      <div className="ctx-divider" />
      <div className="ctx-section-lbl">Your mark</div>
      {ANNOTATION_OPTIONS.map(({ v }) => {
        const meta = CLASS_META[v];
        const selected = userClass === v;
        return (
          <button key={v} className={`ctx-cls ${selected ? "on" : ""}`}
            style={{ "--clr": meta.color }}
            onClick={() => onClassify(v)}
          >
            <span className="ctx-radio">{selected ? "●" : "○"}</span>
            {meta.glyph
              ? <span className="ctx-glyph" style={{ color: meta.color }}>{meta.glyph}</span>
              : <span className="ctx-glyph-empty" />
            }
            <span className="ctx-cls-label">{meta.label}</span>
          </button>
        );
      })}
      <div className="ctx-divider" />
      <button className="ctx-action" onClick={onAskCoach}>
        <span className="ctx-icon">✦</span> Ask coach about this
      </button>
      <button className="ctx-action" onClick={onAddNote}>
        <span className="ctx-icon">✎</span> Add note…
      </button>
      <style>{`
        .ml-ctx {
          position: fixed; z-index: 9999;
          background: var(--surface); border: 1px solid var(--border-2);
          border-radius: var(--radius); box-shadow: var(--shadow-2);
          min-width: 210px; padding: 4px 0;
          font-family: var(--font-ui); font-size: 12px;
        }
        .ctx-head { padding: 8px 12px 6px; }
        .ctx-move { display: block; font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--text); }
        .ctx-engine-verdict { display: block; font-size: 11px; margin-top: 3px; font-family: var(--font-mono); }
        .ctx-divider { height: 1px; background: var(--border); margin: 4px 0; }
        .ctx-section-lbl { padding: 2px 12px 4px; font-size: 10px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.6px; }
        .ctx-cls {
          display: flex; align-items: center; gap: 8px;
          width: 100%; padding: 5px 12px;
          background: none; border: none; cursor: pointer;
          color: var(--text-muted); font-family: var(--font-ui); text-align: left;
          transition: background 0.1s; font-size: 12px;
        }
        .ctx-cls:hover { background: var(--surface-2); }
        .ctx-cls.on { color: var(--clr); }
        .ctx-radio { font-size: 10px; width: 14px; flex-shrink: 0; color: var(--text-dim); }
        .ctx-cls.on .ctx-radio { color: var(--clr); }
        .ctx-glyph { font-family: var(--font-mono); font-size: 11px; width: 22px; }
        .ctx-glyph-empty { width: 22px; display: inline-block; }
        .ctx-cls-label { flex: 1; }
        .ctx-action {
          display: flex; align-items: center; gap: 8px;
          width: 100%; padding: 6px 12px;
          background: none; border: none; cursor: pointer;
          color: var(--text-muted); font-family: var(--font-ui); text-align: left;
          transition: background 0.1s, color 0.1s; font-size: 12px;
        }
        .ctx-action:hover { background: var(--surface-2); color: var(--accent); }
        .ctx-icon { width: 14px; text-align: center; }
      `}</style>
    </div>
  );
}

function NotePopover({ x, y, value, onChange, onClose }) {
  const taRef = useRef(null);
  useEffect(() => { taRef.current?.focus(); }, []);

  return (
    <div className="ml-note-pop" style={{ left: x, top: y }}>
      <div className="note-hd">Note</div>
      <textarea
        ref={taRef}
        className="note-ta"
        placeholder="Your thoughts on this move…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } }}
        rows={3}
      />
      <style>{`
        .ml-note-pop {
          position: fixed; z-index: 9999;
          background: var(--surface); border: 1px solid var(--border-2);
          border-radius: var(--radius); box-shadow: var(--shadow-2);
          width: 240px; padding: 8px;
        }
        .note-hd { font-size: 10px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px; font-family: var(--font-ui); }
        .note-ta {
          width: 100%; box-sizing: border-box;
          background: var(--bg); border: 1px solid var(--border);
          border-radius: var(--radius-sm); color: var(--text);
          font-family: var(--font-ui); font-size: 12px; padding: 6px 8px;
          resize: none; outline: none; line-height: 1.5;
          transition: border-color 0.15s;
        }
        .note-ta:focus { border-color: var(--accent); }
      `}</style>
    </div>
  );
}

function MoveChip({ m, active, onClick, onContextMenu, blind, ply, userAnnotation }) {
  const engineMeta = CLASS_META[m.class] || CLASS_META.ok;
  const userClass = userAnnotation?.classification;
  const userMeta = userClass ? CLASS_META[userClass] : null;
  const hasNote = !!userAnnotation?.thought;

  let glyphNode = null;
  if (blind) {
    if (userMeta?.glyph) {
      glyphNode = <span className="mc-glyph" style={{ color: userMeta.color }}>{userMeta.glyph}</span>;
    }
  } else {
    const bothGlyphs = userMeta?.glyph && engineMeta.glyph;
    if (bothGlyphs && userClass === m.class) {
      glyphNode = (
        <>
          <span className="mc-glyph" style={{ color: engineMeta.color }}>{engineMeta.glyph}</span>
          <span className="mc-match">✓</span>
        </>
      );
    } else if (bothGlyphs) {
      glyphNode = (
        <>
          <span className="mc-glyph mc-user-glyph" style={{ color: userMeta.color }}>{userMeta.glyph}</span>
          <span className="mc-glyph" style={{ color: engineMeta.color }}>{engineMeta.glyph}</span>
        </>
      );
    } else if (userMeta?.glyph) {
      glyphNode = <span className="mc-glyph" style={{ color: userMeta.color }}>{userMeta.glyph}</span>;
    } else if (engineMeta.glyph) {
      glyphNode = <span className="mc-glyph" style={{ color: engineMeta.color }}>{engineMeta.glyph}</span>;
    }
  }

  return (
    <button
      className={`mc ${active ? "active" : ""} ${!blind ? `cls-${m.class}` : ""} ${m.isCritical && !blind ? "critical" : ""}`}
      onClick={onClick}
      onContextMenu={onContextMenu}
      data-ply={ply}
    >
      <span className="mc-san">{m.san}</span>
      {glyphNode}
      {hasNote && <span className="mc-note-ind" title="Has note">✎</span>}
      {m.isCritical && !blind && <span className="mc-dot" />}
      <style>{`
        .mc {
          display: inline-flex; align-items: center; gap: 3px;
          background: none; border: 1px solid transparent; border-radius: 3px;
          padding: 2px 6px; font: inherit; color: var(--text-muted);
          cursor: pointer; text-align: left; position: relative;
          transition: background 0.1s, color 0.1s;
        }
        .mc:hover { background: var(--surface-2); color: var(--text); }
        .mc.active { background: var(--accent); color: #0b0c0d !important; font-weight: 600; }
        .mc.active .mc-glyph, .mc.active .mc-match, .mc.active .mc-note-ind { color: #0b0c0d !important; }
        .mc.cls-blunder    { color: var(--danger); }
        .mc.cls-mistake    { color: var(--warn); }
        .mc.cls-inaccuracy { color: #dcb75a; }
        .mc.cls-brilliant  { color: #7ab9ff; font-weight: 600; }
        .mc.cls-best       { color: var(--accent); }
        .mc.critical { outline: 1px dashed var(--warn); outline-offset: -1px; }
        .mc-glyph { font-size: 11px; }
        .mc-user-glyph { opacity: 0.6; font-style: italic; }
        .mc-match { font-size: 9px; color: var(--accent); font-weight: 700; }
        .mc-note-ind { font-size: 9px; color: var(--text-dim); opacity: 0.7; }
        .mc-dot {
          position: absolute; top: -2px; right: -2px;
          width: 5px; height: 5px; background: var(--warn);
          border-radius: 50%; border: 1px solid var(--bg-2);
        }
      `}</style>
    </button>
  );
}
