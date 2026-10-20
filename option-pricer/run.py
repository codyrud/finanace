import os

from backend.server import main as start_backend_server


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    # `streamlit run ...` injects Streamlit environment variables, so this file
    # should only be used for the standalone local HTTP server.
    if os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("STREAMLIT_RUNTIME"):
        raise RuntimeError(
            "Use option-pricer/streamlit_app.py for Streamlit. "
            "This file starts the standalone backend server only."
        )
    start_backend_server(host=host, port=port)


if __name__ == "__main__":
    main()
