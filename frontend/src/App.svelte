<script>
  import { onMount, onDestroy } from "svelte";
  import GameList from "./lib/GameList.svelte";
  import Board from "./lib/Board.svelte";
  import MoveList from "./lib/MoveList.svelte";
  import EvalBar from "./lib/EvalBar.svelte";
  import ErrorPanel from "./lib/ErrorPanel.svelte";
  import Chat from "./lib/Chat.svelte";
  import { history, currentIndex, currentGame, currentAnalysis } from "./stores.js";

  let activeTab = "errors";
  let flipped = false;
  let analysing = false;
  let analyseStatus = "";

  async function analyseGame() {
    if (!$currentGame || analysing) return;
    analysing = true;
    analyseStatus = "Starting…";
    try {
      const res = await fetch(`/api/analyse-game/${$currentGame.id}`, { method: "POST" });
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
          if (event.type === "status") analyseStatus = event.message;
          if (event.type === "error") analyseStatus = `Error: ${event.message}`;
          if (event.type === "done") {
            analyseStatus = "";
            // Refresh current game to get errors
            const r = await fetch(`/api/game/${$currentGame.id}`);
            if (r.ok) {
              const data = await r.json();
              currentGame.update(g => ({ ...g, ...data, analysed: 1 }));
            }
          }
        }
      }
    } catch (e) {
      analyseStatus = `Error: ${e.message}`;
    } finally {
      analysing = false;
    }
  }

  function navigate(delta) {
    currentIndex.update((i) => {
      const next = i + delta;
      const len = $history.length;
      if (next < 0 || next >= len) return i;
      currentAnalysis.set(null);
      return next;
    });
  }

  function onKey(e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === "ArrowLeft") navigate(-1);
    if (e.key === "ArrowRight") navigate(1);
  }

  onMount(() => window.addEventListener("keydown", onKey));
  onDestroy(() => window.removeEventListener("keydown", onKey));

  $: canPrev = $currentIndex > 0;
  $: canNext = $currentIndex < $history.length - 1;
  $: errorCount = $currentGame?.errors?.length ?? 0;
</script>

<div class="app">
  <header>
    <a class="logo" href="/">patzer.review</a>
    <nav>
      <a href="/" class="nav-link active">Games</a>
      <a href="/" class="nav-link">Openings</a>
      <span class="nav-sep"></span>
      <a href="/" class="nav-link">Settings</a>
    </nav>
  </header>
  <main>
    <aside class="games-col">
      <GameList />
    </aside>

    <section class="board-col">
      <div class="board-row">
        <EvalBar />
        <div class="board-center">
          <Board {flipped} />
        </div>
      </div>
      <div class="controls">
        <button on:click={() => { currentIndex.set(0); currentAnalysis.set(null); }} disabled={!canPrev} title="First move">⏮</button>
        <button on:click={() => navigate(-1)} disabled={!canPrev} title="Previous move">⏪</button>
        <span class="move-counter">{$currentIndex}/{$history.length > 0 ? $history.length - 1 : 0}</span>
        <button on:click={() => navigate(1)} disabled={!canNext} title="Next move">⏩</button>
        <button on:click={() => { currentIndex.set($history.length - 1); currentAnalysis.set(null); }} disabled={!canNext} title="Last move">⏭</button>
        <button on:click={() => (flipped = !flipped)} class="flip-btn" title="Flip board">⇅</button>
        {#if $currentGame}
          <button on:click={analyseGame} disabled={analysing} class="analyse-btn" title="Analyse game with Stockfish + Claude">
            {#if analysing}{analyseStatus || "Analysing…"}{:else}Analyse{/if}
          </button>
        {/if}
      </div>
      {#if $currentGame}
        <MoveList />
      {/if}
    </section>

    <aside class="analysis-col">
      <div class="tab-bar">
        <button class="tab-btn" class:active={activeTab === "errors"} on:click={() => (activeTab = "errors")}>
          Errors
          {#if errorCount > 0}
            <span class="badge">{errorCount}</span>
          {/if}
        </button>
        <button class="tab-btn" class:active={activeTab === "chat"} on:click={() => (activeTab = "chat")}>
          Chat
        </button>
      </div>
      <div class="tab-content" class:hidden={activeTab !== "errors"}>
        <ErrorPanel />
      </div>
      <div class="tab-content chat-tab" class:hidden={activeTab !== "chat"}>
        <Chat />
      </div>
    </aside>
  </main>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }
  header {
    height: 52px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 20px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .logo {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 500;
    color: var(--accent);
    text-decoration: none;
    letter-spacing: -0.3px;
  }
  nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .nav-link {
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    text-decoration: none;
    font-size: 13px;
    transition: color 0.15s;
  }
  .nav-link:hover,
  .nav-link.active { color: var(--text); }
  .nav-sep {
    width: 1px;
    height: 16px;
    background: var(--border);
    margin: 0 4px;
  }
  main {
    display: grid;
    grid-template-columns: 240px 1fr 300px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    height: calc(100vh - 52px);
  }
  .games-col {
    border-right: 1px solid var(--border);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .board-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px;
    gap: 10px;
    overflow: auto;
  }
  .board-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .board-center { flex-shrink: 0; }
  .controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .controls button {
    width: 36px;
    height: 30px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, color 0.15s;
  }
  .controls button:hover:not(:disabled) {
    background: var(--surface2);
    color: var(--text);
  }
  .controls button:disabled { opacity: 0.3; cursor: default; }
  .flip-btn { margin-left: 4px; }
  .analyse-btn {
    margin-left: 8px;
    width: auto !important;
    padding: 0 12px;
    background: var(--accent-muted) !important;
    color: var(--accent) !important;
    border-color: var(--accent) !important;
    font-size: 12px !important;
  }
  .analyse-btn:hover:not(:disabled) {
    background: var(--accent) !important;
    color: #000 !important;
  }
  .analyse-btn:disabled { opacity: 0.6 !important; cursor: default; }
  .move-counter { font-size: 12px; color: var(--text-dim); min-width: 52px; text-align: center; }
  .analysis-col {
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .tab-bar {
    display: flex;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .tab-btn {
    flex: 1;
    padding: 12px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    font-family: var(--font-ui);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: color 0.15s;
    margin-bottom: -1px;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  .badge {
    background: var(--accent);
    color: #000;
    border-radius: 10px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 600;
  }
  .tab-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 12px;
  }
  .chat-tab { padding: 0; }
  .hidden { display: none !important; }
</style>
