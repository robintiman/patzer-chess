<script>
  import { currentAnalysis } from "../stores.js";

  $: evalCp = $currentAnalysis?.eval_cp ?? null;

  $: whitePercent = evalCp === null
    ? 50
    : Math.max(5, Math.min(95, 50 + evalCp / 10));

  $: evalTop = evalCp === null
    ? "?"
    : evalCp < 0
      ? (evalCp < -9000 ? "-M" : `−${Math.abs(evalCp / 100).toFixed(1)}`)
      : "";

  $: evalBot = evalCp === null
    ? ""
    : evalCp > 0
      ? (evalCp > 9000 ? "M" : `+${(evalCp / 100).toFixed(1)}`)
      : "";
</script>

<div class="eval-bar">
  <div class="eval-top">{evalTop}</div>
  <div class="bar">
    <div class="white-portion" style="height: {whitePercent}%"></div>
  </div>
  <div class="eval-bot">{evalBot}</div>
</div>

<style>
  .eval-bar {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    height: 640px;
  }
  .bar {
    width: 9px;
    flex: 1;
    background: #1a1a1a;
    border: 1px solid var(--border);
    border-radius: 5px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    overflow: hidden;
  }
  .white-portion {
    background: #e8e8e8;
    transition: height 0.45s cubic-bezier(0.4, 0, 0.2, 1);
    width: 100%;
  }
  .eval-top,
  .eval-bot {
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    min-height: 14px;
    text-align: center;
  }
</style>
