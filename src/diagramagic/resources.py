from importlib import resources


def load_cheatsheet() -> str:
    with resources.files(__package__).joinpath("data/AGENTS.md").open("r", encoding="utf-8") as fh:
        return fh.read()


def load_patterns() -> str:
    with resources.files(__package__).joinpath("data/diagramagic_patterns.md").open("r", encoding="utf-8") as fh:
        return fh.read()


def load_prompt() -> str:
    with resources.files(__package__).joinpath("data/diagramagic_prompt.txt").open("r", encoding="utf-8") as fh:
        return fh.read()


def load_skill() -> str:
    with resources.files(__package__).joinpath("data/diagramagic_skill.md").open("r", encoding="utf-8") as fh:
        return fh.read()
