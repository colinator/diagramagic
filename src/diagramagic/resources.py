from importlib import resources


def load_cheatsheet() -> str:
    with resources.files(__package__).joinpath("data/AGENTS.md").open("r", encoding="utf-8") as fh:
        return fh.read()
