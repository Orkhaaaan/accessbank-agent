import { useCallback, useRef, useState } from 'react';
import VoiceRecorder from './VoiceRecorder';

export default function ChatInterface({ apiBase }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Salam! AccessBank AI dəstəyinə xoş gəlmisiniz. Sualınızı yazın və ya mikrofonu basılı saxlayaraq danışın.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [transcription, setTranscription] = useState(null);
  const [meta, setMeta] = useState(null);
  const listRef = useRef(null);

  const scrollDown = useCallback(() => {
    setTimeout(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    }, 50);
  }, []);

  const sendText = async (text) => {
    if (!text.trim() || loading) return;
    setMessages((m) => [...m, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);
    setTranscription(null);
    scrollDown();

    try {
      const res = await fetch(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          channel: 'WEB',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setSessionId(data.session_id);
      setMeta(data);
      setMessages((m) => [...m, { role: 'assistant', content: data.reply, meta: data }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Xəta: ${e.message}. Backend işləyir?` },
      ]);
    } finally {
      setLoading(false);
      scrollDown();
    }
  };

  const sendVoice = async (blob) => {
    setLoading(true);
    const form = new FormData();
    form.append('audio', blob, 'recording.webm');
    if (sessionId) form.append('session_id', sessionId);

    try {
      const res = await fetch(`${apiBase}/api/voice`, {
        method: 'POST',
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Voice failed');
      setSessionId(data.session_id);
      setTranscription(data.transcribed_text);
      setMeta(data);
      setMessages((m) => [
        ...m,
        { role: 'user', content: `🎤 ${data.transcribed_text}`, isVoice: true },
        { role: 'assistant', content: data.reply, meta: data },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Səs xətası: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
      scrollDown();
    }
  };

  return (
    <div className="chat-wrap">
      <div className="chat-panel">
        <div className="messages" ref={listRef}>
          {messages.map((msg, i) => (
            <div key={i} className={`msg ${msg.role}`}>
              <p>{msg.content}</p>
              {msg.meta && (
                <div className="msg-meta">
                  {msg.meta.intent && <span>Intent: {msg.meta.intent}</span>}
                  {msg.meta.sentiment && <span>{msg.meta.sentiment}</span>}
                  {msg.meta.emotion && <span>{msg.meta.emotion}</span>}
                  {msg.meta.urgency_score && <span>Urgency: {msg.meta.urgency_score}/5</span>}
                  {msg.meta.is_critical && <span className="critical">CRITICAL</span>}
                  {msg.meta.case_id && <span>Case #{msg.meta.case_id}</span>}
                </div>
              )}
            </div>
          ))}
          {loading && <div className="msg assistant typing">Yazılır...</div>}
        </div>

        {transcription && (
          <div className="transcription-preview">
            <strong>Transkripsiya:</strong> {transcription}
          </div>
        )}

        <form
          className="input-row"
          onSubmit={(e) => {
            e.preventDefault();
            sendText(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Mesajınızı yazın..."
            disabled={loading}
          />
          <VoiceRecorder onRecordingComplete={sendVoice} disabled={loading} />
          <button type="submit" disabled={loading || !input.trim()}>
            Göndər
          </button>
        </form>
      </div>

      {meta && (
        <aside className="meta-panel">
          <h3>Analiz</h3>
          <dl>
            <dt>Sentiment</dt>
            <dd className={meta.sentiment?.toLowerCase()}>{meta.sentiment || '—'}</dd>
            <dt>Emotion</dt>
            <dd>{meta.emotion || '—'}</dd>
            <dt>Urgency</dt>
            <dd>{meta.urgency_score ?? '—'}/5</dd>
            <dt>Intent</dt>
            <dd>{meta.intent || '—'}</dd>
            {meta.case_id && (
              <>
                <dt>Case</dt>
                <dd>#{meta.case_id}</dd>
              </>
            )}
          </dl>
        </aside>
      )}

      <style>{`
        .chat-wrap { display: grid; grid-template-columns: 1fr 220px; gap: 1rem; }
        @media (max-width: 800px) { .chat-wrap { grid-template-columns: 1fr; } }
        .chat-panel {
          background: white;
          border-radius: 16px;
          border: 1px solid var(--ab-border);
          display: flex;
          flex-direction: column;
          height: 70vh;
          overflow: hidden;
        }
        .messages { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
        .msg { max-width: 85%; padding: 0.75rem 1rem; border-radius: 12px; font-size: 0.95rem; }
        .msg.user { align-self: flex-end; background: var(--ab-orange); color: white; }
        .msg.assistant { align-self: flex-start; background: var(--ab-gray); }
        .msg-meta { margin-top: 0.5rem; font-size: 0.7rem; opacity: 0.8; display: flex; flex-wrap: gap: 0.35rem; gap: 0.35rem; }
        .msg-meta .critical { color: var(--critical); font-weight: 700; }
        .transcription-preview {
          padding: 0.5rem 1rem;
          background: #fff7ed;
          border-top: 1px solid var(--ab-border);
          font-size: 0.9rem;
        }
        .input-row {
          display: flex;
          gap: 0.5rem;
          padding: 1rem;
          border-top: 1px solid var(--ab-border);
        }
        .input-row input { flex: 1; padding: 0.75rem 1rem; border: 1px solid var(--ab-border); border-radius: 10px; }
        .input-row button[type=submit] {
          background: var(--ab-orange);
          color: white;
          border: none;
          padding: 0 1.25rem;
          border-radius: 10px;
          font-weight: 600;
        }
        .meta-panel {
          background: white;
          border-radius: 16px;
          border: 1px solid var(--ab-border);
          padding: 1rem;
          height: fit-content;
        }
        .meta-panel h3 { font-size: 0.9rem; margin-bottom: 0.75rem; }
        .meta-panel dl { font-size: 0.85rem; }
        .meta-panel dt { color: #666; margin-top: 0.5rem; }
        .meta-panel dd.negative { color: var(--negative); }
        .meta-panel dd.positive { color: var(--positive); }
        .typing { opacity: 0.6; }
      `}</style>
    </div>
  );
}
