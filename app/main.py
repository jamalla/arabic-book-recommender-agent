"""Milestone 6 - the chat app: a Gradio UI for the shipped agent, served by FastAPI.

    python -m app.main      # http://localhost:8080   (health check: /health)

One browser chat = one Langfuse session; 👍/👎 on an answer = a user_feedback score on its trace.
The app is open to anyone, so it caps questions per chat, characters per question and the history
sent to the model.
"""
import logging
import os
import uuid

import gradio as gr
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langfuse import get_client

from bookrec.factory import agent_settings, make_agent

load_dotenv()  # locally from .env; on AWS the same variables come from the task definition
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

PORT = int(os.getenv("PORT", "8080"))
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS_PER_CHAT", "15"))
MAX_CHARS = 500         # characters per question
HISTORY_MESSAGES = 10   # earlier messages the model sees

WELCOME = (
    "## 📚 مساعد الكتب العربية\n"
    "أرشّح لك كتبًا **من كتالوج حقيقي** (200 كتاب من متجر جملون)، ولا أخترع عناوين."
)
EXAMPLES = ["أريد رواية تاريخية", "كتاب مبسط عن الفلسفة", "كتب عن تربية الأطفال", "هل عندكم روايات نجيب محفوظ؟"]
PRIVACY = "تُحفظ المحادثات لتحسين جودة المساعد، فلا تكتب معلومات شخصية. 👍/👎 تساعدنا على التحسين."
TOO_LONG = f"رسالتك طويلة جدًا. اكتب طلبك في أقل من {MAX_CHARS} حرف من فضلك."
LIMIT_REACHED = "وصلت إلى الحد الأقصى للأسئلة في هذه المحادثة. اضغط «محادثة جديدة» للبدء من جديد."
ERROR = "عذرًا، حدث خطأ مؤقت. حاول مرة أخرى بعد قليل."

FRAMEWORK, PROMPT_VERSION = agent_settings()
agent = make_agent(FRAMEWORK, PROMPT_VERSION)


def new_chat():
    """A fresh chat: empty screen, empty history, no traces, and a new Langfuse session id."""
    return [], [], {}, str(uuid.uuid4())


def respond(message, messages, traces, session_id):
    """One turn: apply the guards, ask the agent, remember which trace produced the answer."""
    message = (message or "").strip()
    if not message:
        return "", messages, messages, traces
    asked = sum(m["role"] == "user" for m in messages)
    trace_id = None
    if len(message) > MAX_CHARS:
        reply = TOO_LONG
    elif asked >= MAX_QUESTIONS:
        reply = LIMIT_REACHED
    else:
        try:
            result = agent.answer(
                message, history=messages[-HISTORY_MESSAGES:], session_id=session_id, tags=["chat-app"]
            )
            reply, trace_id = result["answer"], result["trace_id"]
        except Exception:
            log.exception("agent failed in session %s", session_id)
            reply = ERROR
    messages = messages + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
    if trace_id:
        traces = {**traces, len(messages) - 1: trace_id}  # key = index of the answer in the chat
    return "", messages, messages, traces


def feedback(traces, event: gr.LikeData):
    """👍/👎 on an answer -> a BOOLEAN user_feedback score on the trace that produced it."""
    index = event.index[0] if isinstance(event.index, (list, tuple)) else event.index
    trace_id = traces.get(index)
    if trace_id is None or not isinstance(event.liked, bool):
        return
    get_client().create_score(
        trace_id=trace_id,
        name="user_feedback",
        value=1 if event.liked else 0,
        data_type="BOOLEAN",
        score_id=f"{trace_id}-user_feedback",  # changing the vote overwrites it instead of adding one
    )


def build_ui():
    with gr.Blocks(title="مساعد الكتب العربية", fill_height=True) as demo:
        messages, traces, session_id = gr.State([]), gr.State({}), gr.State("")
        chatbot = gr.Chatbot(rtl=True, placeholder=WELCOME, buttons=["copy"], scale=1, show_label=False)
        question = gr.Textbox(
            placeholder="اكتب طلبك هنا…", show_label=False, rtl=True, max_length=MAX_CHARS,
            submit_btn="إرسال", autofocus=True,
        )
        gr.Examples(EXAMPLES, inputs=question)
        restart = gr.Button("محادثة جديدة", size="sm")
        gr.Markdown(f"{PRIVACY}  \n<small>{FRAMEWORK} · prompt {PROMPT_VERSION} · {agent.model}</small>", rtl=True)

        chat_state = [chatbot, messages, traces, session_id]
        demo.load(new_chat, outputs=chat_state)
        restart.click(new_chat, outputs=chat_state)
        question.submit(respond, [question, messages, traces, session_id], [question, chatbot, messages, traces])
        chatbot.like(feedback, inputs=traces)
    return demo


def create_server():
    """FastAPI in front of Gradio, so the load balancer gets a cheap /health endpoint."""
    server = FastAPI(title="Arabic Book Recommender")

    @server.get("/health")
    def health():
        return {"status": "ok", "agent": FRAMEWORK, "prompt": PROMPT_VERSION}

    return gr.mount_gradio_app(server, build_ui().queue(default_concurrency_limit=8), path="/")


if __name__ == "__main__":
    # Behind the AWS load balancer: trust its X-Forwarded-* headers so Gradio builds https:// links.
    uvicorn.run(create_server(), host="0.0.0.0", port=PORT, proxy_headers=True, forwarded_allow_ips="*")
