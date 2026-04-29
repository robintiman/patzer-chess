// AI Coach right-rail. Chat-first: persistent chat + collapsible position strip.
import { useState, useEffect, useRef } from "react";
import { CLASS_META } from "./MoveList";
import { formatEval } from "./EvalGraph";

export default function CoachPanel({
  currentPly, plies, game, moveData,
  blindMode, gameDbId,
  triggerAsk, onTriggerAskConsumed,
  currentFen,
  playerRating,
  tutorialMode, tutorialFen, currentTutorialStep, tutorialFeedback,
  onStartTutorial, onExitTutorial, onSubmitTutorialMove,
}) {
  const plyInfo = plies[currentPly];
  const moveDetails = moveData;

  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [stripExpanded, setStripExpanded] = useState(false);
  const lastAutoMsgPly = useRef(null);

  // Reset chat when game changes
  useEffect(() => {
    setMessages([]);
    lastAutoMsgPly.current = null;
  }, [gameDbId]);

  // Proactive coach message on critical ply navigation
  useEffect(() => {
    if (!moveDetails?.isCritical || !plyInfo) return;
    if (lastAutoMsgPly.current === currentPly) return;
    lastAutoMsgPly.current = currentPly;
    const san = plyInfo.san;
    const mn = `${plyInfo.moveNo}${plyInfo.color === "w" ? "." : "…"} ${san}`;
    const msg = blindMode
      ? `Something happened on move ${mn}. Take your time — what did you see?`
      : `Move ${mn} was ${CLASS_META[moveDetails.class]?.label || "notable"}. What were you calculating?`;
    setMessages((m) => [...m, { role: "assistant", text: msg }]);
  }, [currentPly]);

  // External trigger from "Ask coach about this" in context menu
  useEffect(() => {
    if (!triggerAsk) return;
    lastAutoMsgPly.current = currentPly;
    const q = triggerAsk.question;
    setMessages((m) => [...m, { role: "user", text: q }, { role: "assistant", text: "" }]);
    setStreaming(true);
    fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fen: triggerAsk.fen || currentFen || "",
        player_move: triggerAsk.playerMoveUci || "",
        best_move: triggerAsk.bestMoveUci || "",
        eval_drop_cp: triggerAsk.evalDrop || 0,
        concept_name: triggerAsk.conceptName || "",
        rating: parseInt(playerRating) || 1200,
        question: q,
      }),
    }).then((res) => {
      readTeachSse(res,
        (plan) => {
          onStartTutorial?.(plan);
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", text: "", type: "tutorial-active", plan };
            return copy;
          });
        },
        (text) => {
          if (text) setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", text: copy[copy.length - 1].text + text };
            return copy;
          });
        },
        () => setStreaming(false)
      );
    }).catch(() => setStreaming(false));
    onTriggerAskConsumed?.();
  }, [triggerAsk]);

  return (
    <div className="cp-root">
      <CoachHeader plyInfo={plyInfo} moveDetails={moveDetails} blindMode={blindMode} tutorialMode={tutorialMode} />
      <PositionStrip
        plyInfo={plyInfo}
        moveDetails={moveDetails}
        blindMode={blindMode}
        expanded={stripExpanded}
        onToggle={() => setStripExpanded((e) => !e)}
      />
      <ChatPanel
        messages={messages}
        setMessages={setMessages}
        streaming={streaming}
        setStreaming={setStreaming}
        plyInfo={plyInfo}
        moveDetails={moveDetails}
        gameDbId={gameDbId}
        blindMode={blindMode}
        currentFen={currentFen}
        playerRating={playerRating}
        tutorialMode={tutorialMode}
        tutorialFen={tutorialFen}
        currentTutorialStep={currentTutorialStep}
        tutorialFeedback={tutorialFeedback}
        onStartTutorial={onStartTutorial}
        onExitTutorial={onExitTutorial}
        onSubmitTutorialMove={onSubmitTutorialMove}
      />
      <style>{`
        .cp-root { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: var(--surface); border-left: 1px solid var(--border); }
      `}</style>
    </div>
  );
}

// SSE reader for hint/compare endpoints (old format: {text: "..."})
function readSse(response, onChunk, onDone) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  function pump() {
    reader.read().then(({ done, value }) => {
      if (done) { onDone(); return; }
      const text = decoder.decode(value, { stream: true });
      for (const line of text.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") { onDone(); return; }
        try { onChunk(JSON.parse(data)); } catch (_) {}
      }
      pump();
    }).catch(onDone);
  }
  pump();
}

// SSE reader for /api/ask (new format: {type: "text"|"plan", ...})
function readTeachSse(response, onPlan, onText, onDone) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  function pump() {
    reader.read().then(({ done, value }) => {
      if (done) { onDone(); return; }
      const raw = decoder.decode(value, { stream: true });
      for (const line of raw.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") { onDone(); return; }
        try {
          const ev = JSON.parse(data);
          if (ev.type === "plan") onPlan(ev.plan);
          else if (ev.type === "text" && ev.text) onText(ev.text);
        } catch (_) {}
      }
      pump();
    }).catch(onDone);
  }
  pump();
}

function CoachHeader({ plyInfo, moveDetails, blindMode, tutorialMode }) {
  return (
    <div className="cph">
      <div className="cph-left">
        <div className="cph-avatar">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 2a4 4 0 0 0-4 4v1H6a2 2 0 0 0-2 2v3a8 8 0 0 0 16 0V9a2 2 0 0 0-2-2h-2V6a4 4 0 0 0-4-4z"/>
            <circle cx="9" cy="11" r="1" fill="currentColor"/>
            <circle cx="15" cy="11" r="1" fill="currentColor"/>
            <path d="M9 16c1 1 2 1.5 3 1.5s2-.5 3-1.5"/>
          </svg>
        </div>
        <div>
          <div className="cph-name">gg <span className="cph-nameAccent">coach</span></div>
          <div className="cph-mode">
            {tutorialMode
              ? "Tutorial mode · board active"
              : blindMode ? "Blind mode · engine hidden" : "Review mode · engine revealed"}
          </div>
        </div>
      </div>
      {!tutorialMode && plyInfo?.san && (
        <div className="cph-context">
          <span className="cph-move">{plyInfo.moveNo}{plyInfo.color === "w" ? "." : "…"} {plyInfo.san}</span>
          {moveDetails?.isCritical && !blindMode && (
            <span className="cph-crit" title={moveDetails.conceptName}>{CLASS_META[moveDetails.class]?.label}</span>
          )}
          {moveDetails?.isCritical && blindMode && (
            <span className="cph-crit-blind">critical moment</span>
          )}
        </div>
      )}
      <style>{`
        .cph { padding: 14px 16px; border-bottom: 1px solid var(--border); background: var(--bg-2); flex-shrink: 0; }
        .cph-left { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .cph-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--accent-muted); color: var(--accent); display: flex; align-items: center; justify-content: center; border: 1px solid var(--accent-dim); }
        .cph-name { font-size: 13px; font-weight: 600; color: var(--text); font-family: var(--font-serif); font-style: italic; letter-spacing: 0.3px; }
        .cph-nameAccent { color: var(--accent); }
        .cph-mode { font-size: 11px; color: var(--text-dim); font-family: var(--font-mono); }
        .cph-context { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 12px; }
        .cph-move { color: var(--text); font-weight: 600; }
        .cph-crit { margin-left: auto; color: var(--warn); background: var(--warn-muted); border: 1px solid var(--warn); padding: 1px 6px; border-radius: 99px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.4px; }
        .cph-crit-blind { margin-left: auto; color: var(--warn); font-style: italic; font-family: var(--font-serif); font-size: 12px; }
      `}</style>
    </div>
  );
}

function PositionStrip({ plyInfo, moveDetails, blindMode, expanded, onToggle }) {
  if (!moveDetails?.isCritical || !plyInfo?.san) return null;

  const hasEngineDetail = !blindMode && moveDetails?.isCritical;

  return (
    <div className={`ps ${expanded ? "expanded" : ""}`}>
      <button className="ps-bar" onClick={onToggle}>
        {hasEngineDetail ? (
          <>
            <span className="ps-chip" style={{ color: CLASS_META[moveDetails.class]?.color, borderColor: CLASS_META[moveDetails.class]?.color }}>
              {CLASS_META[moveDetails.class]?.label}
            </span>
            {moveDetails.evalBefore != null && moveDetails.evalAfter != null && (
              <span className="ps-eval">
                {formatEval(moveDetails.evalBefore)}
                <span className="ps-arrow">→</span>
                {formatEval(moveDetails.evalAfter)}
              </span>
            )}
          </>
        ) : (
          <span className="ps-blind-label">Critical moment · engine hidden</span>
        )}
        <span className="ps-toggle">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && hasEngineDetail && (
        <div className="ps-detail">
          {moveDetails.comment && <p className="ps-comment">{moveDetails.comment}</p>}
          {moveDetails.bestMoveUci && (
            <div className="ps-best">
              Best move: <span className="ps-best-move">{moveDetails.bestMoveUci}</span>
            </div>
          )}
        </div>
      )}
      <style>{`
        .ps { border-bottom: 1px solid var(--border); background: var(--bg-2); flex-shrink: 0; }
        .ps-bar { display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 14px; background: none; border: none; cursor: pointer; text-align: left; }
        .ps-bar:hover { background: var(--surface-2); }
        .ps-chip { font-size: 10px; font-weight: 600; padding: 1px 6px; border: 1px solid; border-radius: 99px; text-transform: uppercase; letter-spacing: 0.4px; }
        .ps-eval { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); display: inline-flex; gap: 4px; align-items: center; }
        .ps-arrow { color: var(--text-dim); }
        .ps-blind-label { font-size: 11px; color: var(--text-dim); font-family: var(--font-serif); font-style: italic; }
        .ps-toggle { margin-left: auto; font-size: 9px; color: var(--text-dim); }
        .ps-detail { padding: 0 14px 10px; }
        .ps-comment { margin: 0 0 6px; font-size: 12px; line-height: 1.55; color: var(--text); font-family: var(--font-serif); font-style: italic; }
        .ps-best { font-size: 11px; color: var(--text-muted); }
        .ps-best-move { font-family: var(--font-mono); color: var(--accent); font-style: normal; }
      `}</style>
    </div>
  );
}

function ChatPanel({
  messages, setMessages, streaming, setStreaming,
  plyInfo, moveDetails, gameDbId, blindMode,
  currentFen,
  playerRating, tutorialMode, tutorialFen, currentTutorialStep, tutorialFeedback,
  onStartTutorial, onExitTutorial, onSubmitTutorialMove,
}) {
  const [input, setInput] = useState("");
  const feedRef = useRef(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function appendToLast(text) {
    setMessages((m) => {
      const copy = [...m];
      copy[copy.length - 1] = { role: "assistant", text: copy[copy.length - 1].text + text };
      return copy;
    });
  }

  function send(question) {
    const q = (question ?? input).trim();
    if (!q || streaming) return;
    if (question == null) setInput("");
    setMessages((m) => [...m, { role: "user", text: q }, { role: "assistant", text: "" }]);
    setStreaming(true);

    fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fen: moveDetails?.fenBefore || currentFen || "",
        player_move: moveDetails?.playerMoveUci || "",
        best_move: moveDetails?.bestMoveUci || "",
        eval_drop_cp: moveDetails?.evalDrop || 0,
        concept_name: moveDetails?.conceptName || "",
        rating: parseInt(playerRating) || 1200,
        question: q,
      }),
    }).then((res) => {
      readTeachSse(res,
        (plan) => {
          onStartTutorial?.(plan);
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", text: "", type: "tutorial-active", plan };
            return copy;
          });
        },
        (text) => { if (text) appendToLast(text); },
        () => setStreaming(false)
      );
    }).catch(() => {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", text: "Sorry, couldn't reach the coach right now." };
        return copy;
      });
      setStreaming(false);
    });
  }

  function getHint() {
    if (!gameDbId || !moveDetails?.fenBefore) { send("Give me a hint about this position."); return; }
    setMessages((m) => [...m, { role: "user", text: "Give me a hint." }, { role: "assistant", text: "" }]);
    setStreaming(true);
    fetch(`/api/games/${gameDbId}/review/hint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fen: moveDetails.fenBefore,
        move_number: moveDetails.moveNo || 0,
        player_move: moveDetails.playerMoveUci || "",
        user_thought: "",
      }),
    }).then((res) => {
      readSse(res, ({ text }) => { if (text) appendToLast(text); }, () => setStreaming(false));
    }).catch(() => setStreaming(false));
  }

  function showBestLine() {
    const line = moveDetails?.bestLine;
    if (!line?.length) return;
    const base = moveDetails.moveNo || 1;
    const formatted = line.map((san, i) => {
      const mn = Math.floor(i / 2) + base;
      return `${mn}${i % 2 === 0 ? "." : "…"} ${san}`;
    }).join("  ");
    setMessages((m) => [
      ...m,
      { role: "user", text: "Show me what should have happened." },
      { role: "assistant", text: `Best continuation: ${formatted}` },
    ]);
  }

  const isCritical = moveDetails?.isCritical;
  const hasBestLine = !blindMode && moveDetails?.bestLine?.length > 0;
  const isQuestionStep = tutorialMode && currentTutorialStep?.type === "question";

  return (
    <div className="chat">
      <div className="chat-feed" ref={feedRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <p className="chat-empty-text">Navigate to a position and ask me anything, or right-click any move to annotate it.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.text
              ? m.text
              : (m.role === "assistant" && streaming && i === messages.length - 1)
                ? <span className="typing-dots"><span /><span /><span /></span>
                : null}
            {m.type === "tutorial-active" && !streaming && (
              <button className="chip chip-exit" onClick={onExitTutorial}>
                Exit tutorial
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Tutorial question participation chips */}
      {isQuestionStep && (
        <div className="chat-chips">
          <span className="chip-label">Your turn:</span>
          {currentTutorialStep.participation_mode === "choice"
            ? currentTutorialStep.choices?.map((san) => (
                <button key={san} className="chip chip-primary" disabled={streaming}
                  onClick={() => onSubmitTutorialMove?.(san)}>
                  {san}
                </button>
              ))
            : <span className="chip-freeplay">Find the move on the board</span>
          }
          {tutorialFeedback && (
            <span className="chip-feedback" style={{ color: tutorialFeedback.correct ? "var(--accent)" : "var(--warn)" }}>
              {tutorialFeedback.message}
            </span>
          )}
        </div>
      )}

      {/* Tutorial question prompt */}
      {isQuestionStep && currentTutorialStep.prompt && (
        <div className="tutorial-prompt">
          {currentTutorialStep.prompt}
        </div>
      )}

      {/* Regular position chips */}
      {!tutorialMode && isCritical && (
        <div className="chat-chips">
          <button className="chip" onClick={getHint} disabled={streaming}>Get a hint</button>
          {hasBestLine && (
            <button className="chip" onClick={showBestLine} disabled={streaming}>Show best line</button>
          )}
          <button className="chip" onClick={() => send("Why was this move bad?")} disabled={streaming}>
            Why was this bad?
          </button>
        </div>
      )}

      <div className="chat-input-row">
        <textarea
          className="chat-ta"
          placeholder="Ask about this position…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={2}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        <button className="chat-send" onClick={() => send()} disabled={!input.trim() || streaming}>→</button>
      </div>

      <style>{`
        .chat { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
        .chat-feed { flex: 1; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; }
        .chat-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 24px; text-align: center; color: var(--text-dim); }
        .chat-empty-icon { opacity: 0.3; }
        .chat-empty-text { font-size: 12px; line-height: 1.6; font-family: var(--font-serif); font-style: italic; max-width: 200px; margin: 0; }
        .chat-bubble { max-width: 90%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.55; white-space: pre-wrap; font-family: var(--font-serif); }
        .chat-bubble.user { align-self: flex-end; background: var(--accent); color: #0b0c0d; border-bottom-right-radius: 3px; font-family: var(--font-ui); }
        .chat-bubble.assistant { align-self: flex-start; background: var(--surface-2); border: 1px solid var(--border); color: var(--text); border-bottom-left-radius: 3px; }
        .typing-dots { display: inline-flex; gap: 3px; align-items: center; }
        .typing-dots span { width: 5px; height: 5px; border-radius: 50%; background: var(--text-dim); animation: td-bounce 1.2s infinite; }
        .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes td-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }
        .chat-chips { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 14px; border-top: 1px solid var(--border); flex-shrink: 0; align-items: center; }
        .chip { background: var(--surface-2); border: 1px solid var(--border); border-radius: 99px; padding: 3px 9px; font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); cursor: pointer; transition: all 0.12s; }
        .chip:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-muted); }
        .chip:disabled { opacity: 0.4; cursor: default; }
        .chip-primary { border-color: var(--accent); color: var(--accent); }
        .chip-primary:hover:not(:disabled) { background: var(--accent); color: #0b0c0d; }
        .chip-exit { display: block; margin-top: 8px; font-family: var(--font-mono); font-size: 10px; background: none; border: 1px solid var(--border); border-radius: 99px; padding: 2px 8px; color: var(--text-dim); cursor: pointer; }
        .chip-exit:hover { border-color: var(--text-muted); color: var(--text-muted); }
        .chip-label { font-size: 10px; color: var(--text-dim); font-family: var(--font-mono); padding: 3px 0; }
        .chip-freeplay { font-size: 11px; color: var(--accent); font-family: var(--font-serif); font-style: italic; padding: 3px 4px; }
        .chip-feedback { font-size: 11px; font-family: var(--font-serif); padding: 3px 4px; }
        .tutorial-prompt { padding: 6px 14px 8px; font-size: 12px; color: var(--text); font-family: var(--font-serif); font-style: italic; line-height: 1.5; border-top: 1px solid var(--border); flex-shrink: 0; background: var(--accent-muted); }
        .chat-input-row { display: flex; gap: 6px; padding: 10px 12px; border-top: 1px solid var(--border); flex-shrink: 0; background: var(--bg-2); }
        .chat-ta { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-family: var(--font-ui); font-size: 13px; padding: 8px 10px; resize: none; outline: none; line-height: 1.4; transition: border-color 0.15s; }
        .chat-ta:focus { border-color: var(--accent); }
        .chat-send { width: 38px; height: 38px; align-self: flex-end; background: var(--accent); color: #0b0c0d; border: none; border-radius: var(--radius-sm); font-size: 16px; font-weight: 600; cursor: pointer; transition: filter 0.12s; flex-shrink: 0; }
        .chat-send:hover:not(:disabled) { filter: brightness(1.08); }
        .chat-send:disabled { opacity: 0.5; cursor: default; }
      `}</style>
    </div>
  );
}
