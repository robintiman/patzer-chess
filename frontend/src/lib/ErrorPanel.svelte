<script>
  import { currentError, currentAnalysis, currentFen } from "../stores.js";

  let analysing = false;

  async function analysePosition() {
    analysing = true;
    try {
      const res = await fetch("/api/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fen: $currentFen, depth: 14 }),
      });
      if (res.ok) {
        currentAnalysis.set(await res.json());
      }
    } finally {
      analysing = false;
    }
  }

  $: themes = $currentError?.concept_name?.trim().split(/[\s,]+/).filter(Boolean) ?? [];
  $: evalDrop = $currentError?.eval_drop_cp ?? null;
  $: bestMove = $currentAnalysis?.best_move ?? $currentError?.best_move ?? null;
  $: pvLine = $currentError?.pv_san ?? $currentAnalysis?.pv?.join(" ") ?? "";
</script>

<div class="panel">
  <button class="analyse-btn" on:click={analysePosition} disabled={analysing}>
    {analysing ? "Analysing…" : "Analyse Position"}
  </button>

  {#if $currentError}
    <div class="error-card">
      <div class="card-header">
        <div class="move-badge">{$currentError.move_number}. {$currentError.player_move}</div>
        {#if evalDrop !== null}
          <div class="eval-drop-chip">▼ −{(evalDrop / 100).toFixed(1)}</div>
        {/if}
      </div>

      {#if $currentError.concept_explanation}
        <p class="description">{$currentError.concept_explanation}</p>
      {/if}

      {#if themes.length > 0}
        <div class="themes">
          {#each themes as theme}
            <span class="theme-tag">{theme}</span>
          {/each}
        </div>
      {/if}

      {#if bestMove}
        <div class="best-move-row">
          <span class="best-label">Best move</span>
          <span class="best-value">{bestMove}</span>
        </div>
      {/if}

      {#if pvLine}
        <div class="pv-line">{pvLine}</div>
      {/if}

    </div>
  {:else}
    <div class="empty-state">No error at this position</div>
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
    overflow-y: auto;
  }
  .analyse-btn {
    padding: 9px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    font-family: var(--font-ui);
    width: 100%;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }
  .analyse-btn:hover:not(:disabled) {
    background: var(--accent-muted);
    border-color: var(--accent);
    color: var(--accent);
  }
  .analyse-btn:disabled { opacity: 0.5; cursor: default; }
  .error-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .move-badge {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 3px 8px;
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--text);
  }
  .eval-drop-chip {
    background: rgba(192,57,43,0.15);
    border: 1px solid rgba(192,57,43,0.3);
    color: #e74c3c;
    border-radius: var(--radius-sm);
    padding: 3px 8px;
    font-size: 13px;
    font-weight: 600;
    font-family: var(--font-mono);
  }
  .description {
    margin: 0;
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.55;
  }
  .themes {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .theme-tag {
    background: var(--accent-muted);
    color: var(--accent);
    border: 1px solid rgba(129,182,76,0.3);
    border-radius: var(--radius-sm);
    padding: 2px 8px;
    font-size: 12px;
  }
  .best-move-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .best-label {
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-dim);
    letter-spacing: 0.5px;
  }
  .best-value {
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--text);
  }
  .pv-line {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-dim);
    font-size: 14px;
    padding: 20px;
    text-align: center;
  }
</style>
