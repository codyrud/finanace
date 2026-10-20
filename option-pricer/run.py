import sys

from backend.server import main as start_backend_server


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    # `streamlit run ...` imports the streamlit package before executing the
    # target script, so this guard prevents the backend HTTP server from trying
    # to bind a port when the app is being hosted by Streamlit.
    if "streamlit" in sys.modules:
        print("Skipping local backend server startup because Streamlit is hosting this app.")
        return
    start_backend_server(host=host, port=port)


if __name__ == "__main__":
    main()
