<script>
  import { onMount } from "svelte";
  import { games, currentGame, history, currentIndex, currentAnalysis, chatMessages } from "../stores.js";
  import { Chess } from "chess.js";

  const username = "jumpyfile";
  let loading = false;
  let syncStatus = "";
  let error = "";

  onMount(() => syncAndFetch());

  async function syncAndFetch() {
    loading = true;
    syncStatus = "Connecting…";
    error = "";
    try {
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, max_games: 20 }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          const match = chunk.match(/^data: (.+)$/m);
          if (!match) continue;
          const event = JSON.parse(match[1]);
          if (event.type === "status") syncStatus = event.message;
          if (event.type === "error") error = event.message;
          if (event.type === "done") syncStatus = "";
        }
      }
    } catch (e) {
      error = e.message;
    }
    await fetchGames();
    loading = false;
  }

  async function fetchGames() {
    try {
      const res = await fetch(`/api/games?username=${encodeURIComponent(username)}`);
      if (!res.ok) throw new Error("Failed to fetch games");
      games.set(await res.json());
    } catch (e) {
      error = e.message;
    }
  }

  async function selectGame(game) {
    const res = await fetch(`/api/game/${game.id}`);
    if (!res.ok) return;
    const data = await res.json();

    const chess = new Chess();
    chess.loadPgn(data.pgn);
    const moves = chess.history({ verbose: true });

    const chess2 = new Chess();
    const hist = [{ fen: chess2.fen(), san: null, uci: null, move_number: 0 }];
    for (const m of moves) {
      chess2.move(m);
      hist.push({ fen: chess2.fen(), san: m.san, uci: m.from + m.to + (m.promotion || ""), move_number: m.color === "w" ? Math.ceil(hist.length / 2) : Math.floor(hist.length / 2) });
    }

    currentGame.set({ ...game, ...data });
    history.set(hist);
    currentIndex.set(0);
    currentAnalysis.set(null);
    chatMessages.set([]);
  }

  function formatDate(d) {
    if (!d) return "";
    return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function initials(name) {
    if (!name || name === "?") return "?";
    return name.slice(0, 2).toUpperCase();
  }

  function resultClass(result) {
    if (!result) return "draw";
    const r = result.toLowerCase();
    if (r === "1-0" || r === "win") return "win";
    if (r === "0-1" || r === "loss") return "loss";
    return "draw";
  }

  function resultLabel(result) {
    if (!result) return "D";
    const r = result.toLowerCase();
    if (r === "1-0" || r === "win") return "W";
    if (r === "0-1" || r === "loss") return "L";
    return "D";
  }
</script>

<div class="game-list">
  <div class="panel-header">
    <span class="panel-title">Recent Games</span>
    {#if $games.length > 0}
      <span class="game-count">{$games.length}</span>
    {/if}
  </div>
  {#if loading}
    <div class="loading-hint">{syncStatus || "Loading…"}</div>
  {/if}

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <ul>
    {#each $games as game (game.id)}
      {@const rc = resultClass(game.result)}
      <li>
        <button class="game-item" class:active={$currentGame?.id === game.id} on:click={() => selectGame(game)}>
          <div class="game-top">
            <div class="avatars">
              <div class="avatar avatar-you" title={username}>{initials(username)}</div>
              <div class="avatar avatar-opp" title={game.opponent ?? "?"}>{initials(game.opponent ?? "?")}</div>
            </div>
            <div class="game-info">
              <div class="game-vs">
                <span class="player-name">{username || "You"}</span>
                <span class="vs">vs</span>
                <span class="player-name">{game.opponent ?? "?"}</span>
              </div>
            </div>
            <span class="result-chip {rc}">{resultLabel(game.result)}</span>
          </div>
          <div class="game-bottom">
            <span class="game-date">{formatDate(game.played_at)}</span>
            {#if game.time_control}
              <span class="time-control">{game.time_control}</span>
            {/if}
            {#if game.error_count > 0}
              <span class="error-badge">⚠ {game.error_count}</span>
            {/if}
          </div>
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .game-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px 6px;
    flex-shrink: 0;
  }
  .panel-title {
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-dim);
  }
  .game-count {
    font-size: 11px;
    color: var(--text-dim);
    background: var(--surface2);
    border-radius: 10px;
    padding: 1px 7px;
  }
  .loading-hint {
    padding: 4px 12px 8px;
    font-size: 12px;
    color: var(--text-dim);
    flex-shrink: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  li {
    list-style: none;
  }
  .game-item {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-bottom: 1px solid var(--border);
    border-left: 2px solid transparent;
    padding: 10px 12px;
    cursor: pointer;
    color: inherit;
    font: inherit;
    transition: background 0.12s;
  }
  .game-item:hover { background: var(--surface2); }
  .game-item.active {
    background: var(--accent-muted);
    border-left-color: var(--accent);
  }
  .game-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .avatars {
    display: flex;
    flex-shrink: 0;
  }
  .avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 600;
    border: 2px solid var(--bg);
  }
  .avatar-you {
    background: #2e4a1c;
    color: var(--accent);
    z-index: 1;
  }
  .avatar-opp {
    background: var(--surface2);
    color: var(--text-muted);
    margin-left: -8px;
  }
  .game-info { flex: 1; min-width: 0; }
  .game-vs {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
  }
  .player-name {
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 60px;
  }
  .vs { color: var(--text-dim); font-size: 11px; }
  .result-chip {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
  }
  .result-chip.win { background: rgba(129,182,76,0.2); color: var(--accent); }
  .result-chip.loss { background: rgba(192,57,43,0.2); color: #e74c3c; }
  .result-chip.draw { background: var(--surface2); color: var(--text-dim); }
  .game-bottom {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
  }
  .game-date { color: var(--text-dim); flex: 1; }
  .time-control { color: var(--text-dim); }
  .error-badge { color: #e67e22; font-size: 11px; }
  .error { color: #e74c3c; padding: 8px 12px; font-size: 12px; margin: 0; }
</style>
