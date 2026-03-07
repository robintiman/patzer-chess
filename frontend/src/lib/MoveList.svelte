<script>
  import { history, currentIndex, currentGame, currentAnalysis } from "../stores.js";

  function goTo(idx) {
    currentIndex.set(idx);
    currentAnalysis.set(null);
  }

  function errorGlyph(fen) {
    const err = $currentGame?.errors_by_fen?.[fen];
    if (!err) return "";
    if (err.eval_drop_cp > 300) return "??";
    if (err.eval_drop_cp > 150) return "?";
    return "?!";
  }

  $: pairs = (() => {
    const result = [];
    const moves = $history.slice(1);
    for (let i = 0; i < moves.length; i += 2) {
      result.push({
        number: Math.floor(i / 2) + 1,
        white: { san: moves[i].san, idx: i + 1, fen: moves[i].fen },
        black: moves[i + 1] ? { san: moves[i + 1].san, idx: i + 2, fen: moves[i + 1].fen } : null,
      });
    }
    return result;
  })();
</script>

<div class="move-list">
  {#each pairs as pair}
    <span class="move-number">{pair.number}.</span>
    <span
      class="move"
      class:current={$currentIndex === pair.white.idx}
      class:blunder={!!$currentGame?.errors_by_fen?.[pair.white.fen]}
      on:click={() => goTo(pair.white.idx)}
    >
      {pair.white.san}{errorGlyph(pair.white.fen)}
    </span>
    {#if pair.black}
      <span
        class="move"
        class:current={$currentIndex === pair.black.idx}
        class:blunder={!!$currentGame?.errors_by_fen?.[pair.black.fen]}
        on:click={() => goTo(pair.black.idx)}
      >
        {pair.black.san}{errorGlyph(pair.black.fen)}
      </span>
    {:else}
      <span></span>
    {/if}
  {/each}
</div>

<style>
  .move-list {
    display: grid;
    grid-template-columns: 32px 1fr 1fr;
    gap: 1px 2px;
    padding: 6px 8px;
    font-family: var(--font-mono);
    font-size: 13px;
    overflow-y: auto;
    max-height: 150px;
    background: var(--surface);
    border-radius: var(--radius-sm);
  }
  .move-number {
    color: var(--text-dim);
    user-select: none;
    display: flex;
    align-items: center;
    padding: 2px 0;
  }
  .move {
    cursor: pointer;
    padding: 2px 5px;
    border-radius: 3px;
    display: flex;
    align-items: center;
  }
  .move:hover { background: var(--surface2); }
  .move.current { background: var(--accent); color: #fff; font-weight: 500; }
  .move.blunder { color: #e67e22; }
  .move.current.blunder { color: #fff; }
</style>
