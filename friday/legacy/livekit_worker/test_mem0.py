"""Manual smoke test for Mem0; the web app uses its own local SQLite memory."""

import json
import logging
import os

from dotenv import load_dotenv
from mem0 import MemoryClient

load_dotenv()
user_name = os.getenv("USER_NAME", "").strip() or "Friday user"
mem0 = MemoryClient()


def add_memory() -> None:
    messages_formatted = [
        {"role": "user", "content": "Please remember that I enjoy Linkin Park."},
        {"role": "assistant", "content": "I'll remember that you enjoy Linkin Park."},
    ]
    mem0.add(messages_formatted, user_id=os.getenv("MEM0_USER_ID", user_name))


def get_memory_by_query() -> str:
    query = f"What preferences has {user_name} shared?"
    response = mem0.search(query, user_id=os.getenv("MEM0_USER_ID", user_name))
    results = response.get("results", []) if isinstance(response, dict) else response
    memories = [
        {"memory": result.get("memory", ""), "updated_at": result.get("updated_at", "")}
        for result in (results or [])
        if isinstance(result, dict)
    ]
    memories_str = json.dumps(memories, ensure_ascii=False)
    print(f"Memories: {memories_str}")
    return memories_str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    get_memory_by_query()
