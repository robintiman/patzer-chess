<script>
  import { onMount, onDestroy } from "svelte";
  import { Chessground } from "chessground";
  import { currentFen, currentAnalysis, currentError } from "../stores.js";

  export let flipped = false;

  let el;
  let cg;

  const fileLetters = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const rankNumbers = ["8", "7", "6", "5", "4", "3", "2", "1"];

  $: displayFiles = flipped ? [...fileLetters].reverse() : fileLetters;
  $: displayRanks = flipped ? [...rankNumbers].reverse() : rankNumbers;

  function uciToFromDest(uci) {
    if (!uci || uci.length < 4) return null;
    return { orig: uci.slice(0, 2), dest: uci.slice(2, 4) };
  }

  function updateBoard(fen, analysis, error) {
    if (!cg) return;
    const turnColor = fen.split(" ")[1] === "w" ? "white" : "black";
    const shapes = [];

    if (analysis?.best_move) {
      const fd = uciToFromDest(analysis.best_move);
      if (fd) shapes.push({ orig: fd.orig, dest: fd.dest, brush: "blue" });
    } else if (error?.best_move) {
      const fd = uciToFromDest(error.best_move);
      if (fd) shapes.push({ orig: fd.orig, dest: fd.dest, brush: "blue" });
    }

    if (error?.player_move) {
      const fd = uciToFromDest(error.player_move);
      if (fd) shapes.push({ orig: fd.orig, dest: fd.dest, brush: "red" });
    }

    cg.set({
      fen,
      turnColor,
      movable: { color: undefined, dests: new Map() },
      drawable: { shapes },
    });
  }

  $: if (cg) {
    cg.set({ orientation: flipped ? "black" : "white" });
  }

  onMount(() => {
    cg = Chessground(el, {
      movable: { color: undefined, dests: new Map() },
      draggable: { enabled: false },
      selectable: { enabled: false },
      drawable: { enabled: true, visible: true },
      orientation: flipped ? "black" : "white",
    });

    const unsubscribeFen = currentFen.subscribe((fen) => {
      let analysis, error;
      currentAnalysis.subscribe((a) => (analysis = a))();
      currentError.subscribe((e) => (error = e))();
      updateBoard(fen, analysis, error);
    });

    const unsubscribeAnalysis = currentAnalysis.subscribe((analysis) => {
      let fen, error;
      currentFen.subscribe((f) => (fen = f))();
      currentError.subscribe((e) => (error = e))();
      updateBoard(fen, analysis, error);
    });

    return () => {
      unsubscribeFen();
      unsubscribeAnalysis();
    };
  });

  onDestroy(() => {
    if (cg) cg.destroy();
  });
</script>

<div class="board-with-labels">
  <div class="labels-row">
    <div class="corner"></div>
    {#each displayFiles as f}
      <div class="file-label">{f}</div>
    {/each}
  </div>
  <div class="board-row-wrap">
    <div class="rank-labels">
      {#each displayRanks as r}
        <div class="rank-label">{r}</div>
      {/each}
    </div>
    <div class="board-wrap">
      <div bind:this={el} class="cg-board-wrap"></div>
    </div>
  </div>
</div>

<style>
  @import "chessground/assets/chessground.base.css";
  @import "chessground/assets/chessground.brown.css";
  @import "chessground/assets/chessground.cburnett.css";

  /* Black pieces: white glow to stand out on dark squares */
  :global(.cg-wrap piece.black) {
    filter:
      drop-shadow(0 0 2px rgba(255,255,255,0.85))
      drop-shadow(0 0 4px rgba(255,255,255,0.3));
  }

  /* White pieces: dark glow to stand out on light squares */
  :global(.cg-wrap piece.white) {
    filter:
      drop-shadow(0 0 2px rgba(0,0,0,0.85))
      drop-shadow(0 0 4px rgba(0,0,0,0.3));
  }

  /* Override board squares: dark (#1e1e1e) and white (#f0f0f0) checkerboard */
  :global(cg-board) {
    background-color: #f0f0f0 !important;
    background-image: repeating-conic-gradient(#1e1e1e 0% 25%, #f0f0f0 0% 50%) !important;
    background-size: 25% 25% !important;
  }


  .board-with-labels {
    display: flex;
    flex-direction: column;
  }
  .labels-row {
    display: flex;
    padding-left: 20px;
  }
  .corner { width: 0; flex-shrink: 0; }
  .file-label {
    width: 80px;
    text-align: center;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-dim);
    padding-bottom: 4px;
    user-select: none;
  }
  .board-row-wrap {
    display: flex;
    align-items: stretch;
  }
  .rank-labels {
    display: flex;
    flex-direction: column;
    width: 20px;
    flex-shrink: 0;
  }
  .rank-label {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-dim);
    user-select: none;
  }
  .board-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
  }
  .cg-board-wrap {
    width: 640px;
    height: 640px;
  }
</style>
