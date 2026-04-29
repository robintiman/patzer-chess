import { useMemo } from "react";
import { Chessboard } from "react-chessboard";

function resolveCSSVar(varName) {
  return getComputedStyle(document.body).getPropertyValue(varName).trim();
}

const ARROW_COLOR_MAP = {
  accent: "--accent",
  info:   "--info",
  danger: "--danger",
  warn:   "--warn",
};

function buildSquareStyles({ lastMove, selectedSquare, highlight, highlightKind }) {
  const styles = {};

  if (lastMove?.from)
    styles[lastMove.from] = { backgroundColor: resolveCSSVar("--accent") + "38" };
  if (lastMove?.to)
    styles[lastMove.to] = { backgroundColor: resolveCSSVar("--accent") + "38" };

  if (selectedSquare)
    styles[selectedSquare] = {
      ...(styles[selectedSquare] || {}),
      outline: `3px solid ${resolveCSSVar("--accent")}`,
      outlineOffset: "-3px",
    };

  if (highlight) {
    const color =
      highlightKind === "danger" ? resolveCSSVar("--danger") :
      highlightKind === "best"   ? resolveCSSVar("--accent") :
      highlightKind === "hint"   ? resolveCSSVar("--info")   :
      resolveCSSVar("--warn");
    styles[highlight] = {
      ...(styles[highlight] || {}),
      outline: `3px solid ${color}`,
      outlineOffset: "-3px",
      borderRadius: "3px",
      animation: highlightKind === "critical"
        ? "board-pulse 1.8s ease-in-out infinite" : undefined,
    };
  }

  return styles;
}

function buildCustomArrows(arrows) {
  return arrows
    .filter((a) => a?.from && a?.to)
    .map((a) => ({
      startSquare: a.from,
      endSquare: a.to,
      color: resolveCSSVar(ARROW_COLOR_MAP[a.color] || "--accent") + "CC",
    }));
}

export default function Board({
  fen,
  flipped = false,
  size = 560,
  lastMove = null,
  highlight = null,
  highlightKind = "critical",
  arrows = [],
  showCoords = true,
  onSquareClick = null,
  selectedSquare = null,
  interactive = false,
  onPieceDrop = null,
}) {
  const customSquareStyles = useMemo(
    () => buildSquareStyles({ lastMove, selectedSquare, highlight, highlightKind }),
    [lastMove, selectedSquare, highlight, highlightKind]
  );

  const customArrows = useMemo(() => buildCustomArrows(arrows), [arrows]);

  return (
    <div className="board-root" style={{
      position: "relative", width: size, height: size,
      ...(interactive ? { outline: "2px solid var(--accent)", outlineOffset: "3px", borderRadius: "var(--radius)" } : {}),
    }}>
      <Chessboard options={{
        position: fen,
        boardOrientation: flipped ? "black" : "white",
        boardStyle: { width: size, height: size },
        squareStyles: customSquareStyles,
        arrows: customArrows,
        darkSquareStyle: { backgroundColor: resolveCSSVar("--square-dark") },
        lightSquareStyle: { backgroundColor: resolveCSSVar("--square-light") },
        showNotation: showCoords,
        onSquareClick: onSquareClick ? ({ square }) => onSquareClick(square) : undefined,
        allowDragging: interactive,
        onPieceDrop: interactive && onPieceDrop
          ? ({ sourceSquare, targetSquare }) => { onPieceDrop(sourceSquare + targetSquare); return true; }
          : undefined,
        animationDurationInMs: 250,
      }} />
      <style>{`
        .board-root {
          border-radius: var(--radius);
          overflow: hidden;
          box-shadow: var(--shadow-2);
        }
        @keyframes board-pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

export function EvalBar({ evalCp, height = 560, flipped = false }) {
  const clamped = Math.max(-800, Math.min(800, evalCp ?? 0));
  const whiteShare = 0.5 + clamped / 1600;
  const whitePct = Math.round(whiteShare * 100);
  const label = (() => {
    if (Math.abs(evalCp) >= 1000) return (evalCp > 0 ? "+" : "-") + "M";
    const v = (evalCp / 100).toFixed(1);
    return evalCp > 0 ? `+${v}` : v;
  })();

  return (
    <div className="eval-bar" style={{ height }}>
      <div className="eval-fill-white" style={{
        height: flipped ? `${100 - whitePct}%` : `${whitePct}%`,
        bottom: flipped ? "auto" : 0,
        top: flipped ? 0 : "auto",
      }} />
      <div className={`eval-label ${evalCp >= 0 ? "top" : "bot"} ${evalCp >= 0 ? "on-white" : "on-black"}`}>
        {label}
      </div>
      <style>{`
        .eval-bar {
          position: relative; width: 22px;
          background: #111; border-radius: 3px;
          overflow: hidden;
          box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05);
        }
        .eval-fill-white {
          position: absolute; left: 0; right: 0;
          background: #f5f2e8;
          transition: height 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .eval-label {
          position: absolute; left: 0; right: 0;
          text-align: center;
          font-family: var(--font-mono); font-size: 10px;
          font-weight: 600; letter-spacing: 0.3px;
        }
        .eval-label.top { top: 4px; }
        .eval-label.bot { bottom: 4px; }
        .eval-label.on-white { color: #222; }
        .eval-label.on-black { color: #ddd; }
      `}</style>
    </div>
  );
}
