// Game list sidebar. Shows recent games ranked by learning value.

export default function GameList({ games, activeId, onSelect, username, gamesLoading, onSync, syncing }) {
  const initials = username ? username.slice(0, 2).toUpperCase() : "??";

  return (
    <div className="gl-root">
      <div className="gl-header">
        <div className="gl-title">
          <span className="gl-title-main">Recent games</span>
        </div>
        <button className={`gl-sync${syncing ? " gl-sync--spinning" : ""}`} title="Sync with chess.com"
          onClick={onSync} disabled={syncing}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </div>

      <div className="gl-user-chip">
        <div className="gl-avatar">{initials}</div>
        <div className="gl-user-meta">
          <div className="gl-user-name">{username}</div>
          <div className="gl-user-stats">{games.length} game{games.length !== 1 ? "s" : ""} loaded</div>
        </div>
      </div>

      <div className="gl-list">
        {gamesLoading ? (
          <div className="gl-loading">
            <div className="gl-spinner" />
            <span>Loading games…</span>
          </div>
        ) : games.length === 0 ? (
          <div className="gl-empty">No games found. Sync to import from Chess.com.</div>
        ) : (
          games.map((g) => (
            <GameCard key={g.id} game={g} active={g.id === activeId} onClick={() => onSelect(g.id)} />
          ))
        )}
      </div>

      <style>{`
        .gl-root { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
        .gl-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 14px 16px 10px;
          border-bottom: 1px solid var(--border);
          flex-shrink: 0;
        }
        .gl-title { display: flex; flex-direction: column; gap: 1px; }
        .gl-title-main { font-size: 13px; font-weight: 600; color: var(--text); letter-spacing: 0.2px; }
        .gl-title-sub { font-size: 11px; color: var(--text-dim); font-style: italic; font-family: var(--font-serif); }
        .gl-sync {
          background: none; border: 1px solid var(--border); border-radius: var(--radius-sm);
          color: var(--text-dim); width: 28px; height: 28px;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; transition: color 0.15s, background 0.15s, border-color 0.15s;
        }
        .gl-sync:hover:not(:disabled) { color: var(--text); background: var(--surface-2); border-color: var(--border-2); }
        .gl-sync:disabled { opacity: 0.5; cursor: default; }
        @keyframes gl-spin { to { transform: rotate(360deg); } }
        .gl-sync--spinning svg { animation: gl-spin 0.8s linear infinite; }
        .gl-user-chip {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 16px; border-bottom: 1px solid var(--border); flex-shrink: 0;
        }
        .gl-avatar {
          width: 32px; height: 32px; border-radius: 50%;
          background: var(--accent-muted); color: var(--accent);
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; font-weight: 700; font-family: var(--font-mono);
          border: 1px solid var(--accent-dim);
        }
        .gl-user-meta { flex: 1; min-width: 0; }
        .gl-user-name { font-size: 13px; font-weight: 600; color: var(--text); }
        .gl-user-stats { font-size: 11px; color: var(--text-dim); font-family: var(--font-mono); }
        .gl-list { flex: 1; overflow-y: auto; }
        .gl-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; height: 120px; color: var(--text-dim); font-size: 12px; }
        .gl-spinner { width: 18px; height: 18px; border: 2px solid var(--border-2); border-top-color: var(--accent); border-radius: 50%; animation: gl-spin 0.8s linear infinite; }
        @keyframes gl-spin { to { transform: rotate(360deg); } }
        .gl-empty { padding: 16px; font-size: 12px; color: var(--text-dim); font-style: italic; font-family: var(--font-serif); }
      `}</style>
    </div>
  );
}

function GameCard({ game, active, onClick }) {
  const resultChar = game.result === "win" ? "W" : game.result === "loss" ? "L" : "D";
  const resultColor = game.result === "win" ? "var(--accent)"
    : game.result === "loss" ? "var(--danger)"
    : "var(--text-dim)";
  const learning = Math.round((game.interest || 0) * 100);

  return (
    <button className={`gc ${active ? "active" : ""}`} onClick={onClick}>
      <div className="gc-top">
        <div className="gc-result" style={{ color: resultColor, borderColor: resultColor }}>{resultChar}</div>
        <div className="gc-info">
          <div className="gc-vs">
            <span className="gc-opp">vs. {game.opponent}</span>
            {game.oppRating && <span className="gc-rating">{game.oppRating}</span>}
          </div>
          {game.opening && (
            <div className="gc-opening">{game.opening}</div>
          )}
        </div>
      </div>
      <div className="gc-bottom">
        <div className="gc-meta">
          {game.playedAt && <span className="gc-date">{shortDate(game.playedAt)}</span>}
          {game.playedAt && game.timeControl && <span className="gc-dot">·</span>}
          {game.timeControl && <span className="gc-tc">{game.timeControl}</span>}
          {game.ply && (
            <>
              <span className="gc-dot">·</span>
              <span className="gc-ply">{Math.ceil(game.ply / 2)} moves</span>
            </>
          )}
        </div>
        <div className="gc-badges">
          {game.errorCount > 0 && (
            <span className="gc-badge err">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
              </svg>
              {game.errorCount}
            </span>
          )}
          <LearningPip value={learning} />
          {game.phase === "done" && <span className="gc-badge done">✓</span>}
          {game.phase === "in_progress" && <span className="gc-badge prog">…</span>}
        </div>
      </div>

      <style>{`
        .gc {
          display: block; width: 100%; text-align: left;
          background: none; border: none;
          border-bottom: 1px solid var(--border);
          border-left: 2px solid transparent;
          padding: 12px 16px;
          cursor: pointer; color: inherit; font: inherit;
          transition: background 0.12s, border-left-color 0.12s;
        }
        .gc:hover { background: var(--surface-2); }
        .gc.active { background: var(--accent-muted); border-left-color: var(--accent); }
        .gc-top { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
        .gc-result {
          width: 24px; height: 24px; flex-shrink: 0;
          border-radius: 4px; border: 1px solid;
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; font-weight: 700; font-family: var(--font-mono);
        }
        .gc-info { flex: 1; min-width: 0; }
        .gc-vs { display: flex; align-items: baseline; gap: 6px; font-size: 13px; color: var(--text); }
        .gc-opp { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .gc-rating { font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); }
        .gc-opening {
          font-size: 11px; color: var(--text-muted);
          font-style: italic; font-family: var(--font-serif);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .gc-bottom { display: flex; justify-content: space-between; align-items: center; padding-left: 34px; }
        .gc-meta { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-dim); font-family: var(--font-mono); }
        .gc-dot { opacity: 0.5; }
        .gc-badges { display: flex; align-items: center; gap: 6px; }
        .gc-badge {
          font-size: 10px; font-family: var(--font-mono);
          display: inline-flex; align-items: center; gap: 2px;
          padding: 1px 5px; border-radius: 99px;
        }
        .gc-badge.err { color: var(--warn); background: var(--warn-muted); }
        .gc-badge.done { color: var(--accent); font-size: 11px; }
        .gc-badge.prog { color: var(--warn); font-size: 12px; }
      `}</style>
    </button>
  );
}

function LearningPip({ value }) {
  const bars = 5;
  const filled = Math.max(1, Math.min(bars, Math.round(value / 20)));
  return (
    <span className="pip" title={`Learning value ${value}%`}>
      {Array.from({ length: bars }).map((_, i) => (
        <span key={i} className={`pip-bar ${i < filled ? "on" : ""}`} />
      ))}
      <style>{`
        .pip { display: inline-flex; align-items: flex-end; gap: 1.5px; height: 10px; }
        .pip-bar { width: 2px; background: var(--border-2); border-radius: 1px; }
        .pip-bar:nth-child(1) { height: 3px; }
        .pip-bar:nth-child(2) { height: 5px; }
        .pip-bar:nth-child(3) { height: 7px; }
        .pip-bar:nth-child(4) { height: 9px; }
        .pip-bar:nth-child(5) { height: 11px; }
        .pip-bar.on { background: var(--accent); }
      `}</style>
    </span>
  );
}

function shortDate(iso) {
  const d = new Date(iso + "T00:00:00");
  const today = new Date();
  const diff = Math.round((today - d) / (86400 * 1000));
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return `${diff}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
