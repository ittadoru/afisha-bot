from afishabot.app import create_app

app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("afishabot.main:app", host="0.0.0.0", port=8000)
