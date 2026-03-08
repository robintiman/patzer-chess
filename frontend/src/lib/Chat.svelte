<script>
  import { chatMessages, currentFen, currentError, history, currentIndex } from "../stores.js";

  let question = "";
  let streaming = false;
  let messagesEl;

  $: if ($currentError && !question) {
    question = `Why is ${$currentError.player_move} a blunder here?`;
  }

  $: contextMove = $history[$currentIndex];

  function now() {
    return new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  async function sendQuestion() {
    if (!question.trim() || streaming) return;

    const userMsg = question.trim();
    question = "";
    chatMessages.update((msgs) => [...msgs, { role: "user", text: userMsg, time: now() }]);
    chatMessages.update((msgs) => [...msgs, { role: "assistant", text: "", time: now() }]);

    streaming = true;

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fen: $currentFen,
          player_move: $currentError?.player_move ?? "",
          best_move: $currentError?.best_move ?? "",
          eval_drop_cp: $currentError?.eval_drop_cp ?? 0,
          concept_name: $currentError?.concept_name ?? "",
          question: userMsg,
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") break;
          try {
            const { text } = JSON.parse(payload);
            chatMessages.update((msgs) => {
              const copy = [...msgs];
              copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + text };
              return copy;
            });
          } catch {}
        }
      }
    } catch (e) {
      chatMessages.update((msgs) => {
        const copy = [...msgs];
        copy[copy.length - 1] = { role: "assistant", text: "Error: " + e.message, time: now() };
        return copy;
      });
    } finally {
      streaming = false;
    }
  }

  $: if ($chatMessages.length && messagesEl) {
    setTimeout(() => messagesEl?.scrollTo({ top: messagesEl.scrollHeight, behavior: "smooth" }), 50);
  }
</script>

<div class="chat">
  {#if contextMove?.san}
    <div class="context-chip">Move {contextMove.move_number} · {contextMove.san}</div>
  {/if}
  <div class="messages" bind:this={messagesEl}>
    {#each $chatMessages as msg}
      <div class="bubble-wrap {msg.role}">
        <div class="bubble">
          <p>{msg.text}</p>
        </div>
        {#if msg.time}
          <span class="ts">{msg.time}</span>
        {/if}
      </div>
    {/each}
    {#if streaming}
      <div class="typing-wrap">
        <div class="typing">
          <span></span><span></span><span></span>
        </div>
      </div>
    {/if}
  </div>
  <div class="input-row">
    <textarea
      bind:value={question}
      rows="2"
      placeholder="Ask about this position…"
      on:keydown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), sendQuestion())}
    ></textarea>
    <button class="send-btn" on:click={sendQuestion} disabled={streaming || !question.trim()} title="Send">→</button>
  </div>
</div>

<style>
  .chat {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    height: 100%;
    padding: 10px 12px;
    gap: 8px;
  }
  .context-chip {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 12px;
    color: var(--text-dim);
    align-self: center;
    font-family: var(--font-mono);
    flex-shrink: 0;
  }
  .messages {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 4px 0;
  }
  .bubble-wrap {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-width: 85%;
  }
  .bubble-wrap.user {
    align-self: flex-end;
    align-items: flex-end;
  }
  .bubble-wrap.assistant {
    align-self: flex-start;
    align-items: flex-start;
  }
  .bubble {
    padding: 8px 12px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.5;
  }
  .bubble-wrap.user .bubble {
    background: var(--accent-dim);
    color: #fff;
    border-bottom-right-radius: 4px;
  }
  .bubble-wrap.assistant .bubble {
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    border-bottom-left-radius: 4px;
  }
  .bubble p { margin: 0; white-space: pre-wrap; }
  .ts {
    font-size: 11px;
    color: var(--text-dim);
    padding: 0 4px;
  }
  .typing-wrap { align-self: flex-start; }
  .typing {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 12px;
    border-bottom-left-radius: 4px;
    padding: 10px 14px;
    display: flex;
    gap: 4px;
    align-items: center;
  }
  .typing span {
    width: 6px;
    height: 6px;
    background: var(--text-dim);
    border-radius: 50%;
    animation: bounce 1.2s infinite;
  }
  .typing span:nth-child(2) { animation-delay: 0.2s; }
  .typing span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-5px); }
  }
  .input-row {
    display: flex;
    gap: 6px;
    align-items: flex-end;
    flex-shrink: 0;
  }
  textarea {
    flex: 1;
    padding: 8px 10px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 14px;
    resize: none;
    font-family: var(--font-ui);
    outline: none;
    transition: border-color 0.15s;
  }
  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--text-dim); }
  .send-btn {
    width: 34px;
    height: 34px;
    background: var(--accent);
    border: none;
    border-radius: var(--radius-sm);
    color: #fff;
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
    flex-shrink: 0;
  }
  .send-btn:hover:not(:disabled) { background: var(--accent-dim); }
  .send-btn:disabled { opacity: 0.4; cursor: default; }
</style>
