"""
Minimal WebSocket interview test — runs 2 turns then exits.
Prints every message received from the server.

Usage:
    python test_ws.py <session_id> <jwt_token>

The session must belong to the user the token was issued for (get both via
POST /auth/login or /auth/signup, then POST /sessions).
"""
import asyncio
import json
import sys
import websockets

if len(sys.argv) != 3:
    print("Usage: python test_ws.py <session_id> <jwt_token>")
    sys.exit(1)

SESSION_ID = sys.argv[1]
TOKEN = sys.argv[2]
URI = f"ws://localhost:8000/ws/interview/{SESSION_ID}?token={TOKEN}"
MAX_TURNS = 2


async def run():
    async with websockets.connect(URI) as ws:
        print(f"Connected to {URI}\n")
        turns_done = 0

        while turns_done < MAX_TURNS:
            question_tokens = []

            # Collect tokens until question_end or session_end
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                mtype = msg["type"]

                if mtype == "token":
                    question_tokens.append(msg["content"])
                    print(msg["content"], end="", flush=True)

                elif mtype == "question_end":
                    question = "".join(question_tokens).strip()
                    print(f"\n\n[question_end — turn {turns_done + 1}]")
                    break

                elif mtype == "session_end":
                    print(f"\n\n[session_end] {msg['content']}")
                    return

                elif mtype == "error":
                    print(f"\n[ERROR] {msg['content']}")
                    return

            # Send a canned answer
            answer = "I would use a hash map to achieve O(1) lookup time, trading space for time complexity."
            payload = json.dumps({"content": answer})
            await ws.send(payload)
            print(f"[sent answer] {answer}\n")
            turns_done += 1

        # After MAX_TURNS, wait for one more message (session_end or next question)
        raw = await asyncio.wait_for(ws.recv(), timeout=60)
        msg = json.loads(raw)
        print(f"[post-loop msg] type={msg['type']}")
        if msg["type"] == "token":
            print("(more turns available — exiting early for test)")


asyncio.run(run())
