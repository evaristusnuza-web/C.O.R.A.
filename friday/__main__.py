"""Run Friday locally with ``python -m friday``."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "friday.web_app:app",
        host=os.getenv("FRIDAY_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
