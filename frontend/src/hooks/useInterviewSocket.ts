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

export function useInterviewSocket(sessionId: string) {
  const [status, setStatus] = useState<InterviewStatus>("connecting");
  const [draftQuestion, setDraftQuestion] = useState("");
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [endMessage, setEndMessage] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = getToken();
    const ws = new WebSocket(`${WS_BASE_URL}/ws/interview/${sessionId}?token=${token ?? ""}`);
    socketRef.current = ws;

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
          setEndMessage(msg.content);
          setStatus("ended");
          break;
        case "error":
          setErrorMessage(msg.content);
          setStatus("error");
          break;
      }
    };

    ws.onerror = () => {
      setErrorMessage("Connection error");
      setStatus("error");
    };

    return () => {
      ws.close();
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
    socketRef.current?.close();
  }

  return { status, draftQuestion, turns, errorMessage, endMessage, sendAnswer, disconnect };
}
