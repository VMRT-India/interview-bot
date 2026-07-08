import { useEffect, useRef, useState } from "react";
import { WS_BASE_URL } from "../lib/apiClient";
import { getToken } from "../lib/auth";
import type { ServerWsMessage } from "../lib/types";

export interface InterviewTurn {
  question: string;
  answer: string | null;
}

export type InterviewStatus =
  | "connecting"
  | "streaming_question"
  | "awaiting_answer"
  | "waiting_for_next_question"
  | "ended"
  | "error";

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_BASE_DELAY_MS = 1000;

export function useInterviewSocket(sessionId: string) {
  const [status, setStatus] = useState<InterviewStatus>("connecting");
  const [draftQuestion, setDraftQuestion] = useState("");
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [endMessage, setEndMessage] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const intentionalCloseRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    intentionalCloseRef.current = false;
    reconnectAttemptsRef.current = 0;

    function connect() {
      const token = getToken();
      const ws = new WebSocket(`${WS_BASE_URL}/ws/interview/${sessionId}?token=${token ?? ""}`);
      socketRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data) as ServerWsMessage;
        switch (msg.type) {
          case "token":
            setStatus("streaming_question");
            setDraftQuestion((prev) => prev + msg.content);
            break;
          case "question_end":
            setDraftQuestion((prev) => {
              setTurns((t) => [...t, { question: prev, answer: null }]);
              return "";
            });
            setStatus("awaiting_answer");
            break;
          case "session_end":
            intentionalCloseRef.current = true;
            setEndMessage(msg.content);
            setStatus("ended");
            break;
          case "error":
            intentionalCloseRef.current = true;
            setErrorMessage(msg.content);
            setStatus("error");
            break;
        }
      };

      ws.onclose = () => {
        if (intentionalCloseRef.current) return;
        // Unexpected drop (e.g. a flaky network hop) rather than a normal end/error the
        // server told us about — interview state lives in Redis, not in this connection,
        // so reconnecting to the same session genuinely resumes rather than restarting.
        if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          setErrorMessage("Connection lost. Please refresh to try reconnecting.");
          setStatus("error");
          return;
        }
        reconnectAttemptsRef.current += 1;
        setStatus("connecting");
        const delay = RECONNECT_BASE_DELAY_MS * 2 ** (reconnectAttemptsRef.current - 1);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      socketRef.current?.close();
    };
  }, [sessionId]);

  function sendAnswer(answer: string) {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setTurns((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last) last.answer = answer;
      return next;
    });
    ws.send(JSON.stringify({ content: answer }));
    setStatus("waiting_for_next_question");
  }

  function disconnect() {
    intentionalCloseRef.current = true;
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    socketRef.current?.close();
  }

  return { status, draftQuestion, turns, errorMessage, endMessage, sendAnswer, disconnect };
}
