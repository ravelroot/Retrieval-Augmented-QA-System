import logging

import uvicorn

from nexo.config import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    print(f"\n  Nexo rodando em http://{s.host}:{s.port}\n")
    uvicorn.run("nexo.api.app:app", host=s.host, port=s.port, log_level="info")


if __name__ == "__main__":
    main()
