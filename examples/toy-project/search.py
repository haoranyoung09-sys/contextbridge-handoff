"""A deliberately unfinished search function for the handoff demonstration."""


def search(items: list[str], query: str) -> list[str]:
    """Return exact matches; the next agent can add Unicode case folding."""
    return [item for item in items if query in item]


if __name__ == "__main__":
    print(search(["Straße", "STRASSE", "Python"], "strasse"))
