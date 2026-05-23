import { useRef, useState } from 'react';

export default function VoiceRecorder({ onRecordingComplete, disabled }) {
  const [recording, setRecording] = useState(false);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4',
      });
      chunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        stream.getTracks().forEach((t) => t.stop());
        onRecordingComplete(blob);
      };
      mediaRef.current = { mediaRecorder, stream };
      mediaRecorder.start();
      setRecording(true);
    } catch (e) {
      alert('Mikrofon icazəsi lazımdır.');
    }
  };

  const stopRecording = () => {
    if (mediaRef.current?.mediaRecorder?.state === 'recording') {
      mediaRef.current.mediaRecorder.stop();
    }
    setRecording(false);
  };

  return (
    <button
      type="button"
      className={`mic-btn ${recording ? 'recording' : ''}`}
      disabled={disabled}
      onMouseDown={startRecording}
      onMouseUp={stopRecording}
      onMouseLeave={recording ? stopRecording : undefined}
      onTouchStart={(e) => {
        e.preventDefault();
        startRecording();
      }}
      onTouchEnd={(e) => {
        e.preventDefault();
        stopRecording();
      }}
      title="Basılı saxlayın — danışın, buraxın — göndərin"
    >
      {recording ? '⏺' : '🎤'}
      <style>{`
        .mic-btn {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: 2px solid var(--ab-border);
          background: white;
          font-size: 1.25rem;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .mic-btn.recording {
          background: var(--critical);
          border-color: var(--critical);
          animation: pulse 1s infinite;
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
      `}</style>
    </button>
  );
}
