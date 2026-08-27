from __future__ import annotations
import uvicorn
from dotenv import load_dotenv
load_dotenv()
from app.config.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )

if __name__ == "__main__":
    main()