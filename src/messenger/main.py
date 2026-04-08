import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI()

messages: list[dict] = []
next_id = 1


class MessageIn(BaseModel):
    from_: str = Field(alias="from")
    to: str
    body: str

    model_config = {"populate_by_name": True}


@app.get("/health")
def health():
    return {"status": "alive", "service": "messenger"}


@app.post("/message")
def send_message(msg: MessageIn):
    global next_id
    record = {
        "id": next_id,
        "from": msg.from_,
        "to": msg.to,
        "body": msg.body,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "unread": True,
    }
    messages.append(record)
    sent_id = next_id
    next_id += 1
    return {"status": "sent", "id": sent_id}


@app.get("/messages")
def get_messages(to: str = Query(...), all: Optional[bool] = Query(False)):
    if all:
        result = [m for m in messages if m["to"] == to]
    else:
        result = [m for m in messages if m["to"] == to and m["unread"]]
        for m in result:
            m["unread"] = False
    return {"messages": result}


if __name__ == "__main__":
    port = int(os.environ.get("MESSENGER_PORT", 39052))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
