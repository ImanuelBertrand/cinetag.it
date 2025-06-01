import secrets
from pathlib import Path


def load_words(filename: str) -> list[str]:
    """
    Load words from a data file

    Args:
        filename (str): Name of the file to load

    Returns:
        list: List of words from the file
    """
    data_dir = Path(__file__).parent.parent / "data"
    file_path = data_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path) as f:
        return [line.strip() for line in f if line.strip()]


# Load word lists
ADJECTIVES = load_words("adjectives.txt")
NOUNS = load_words("nouns.txt")
VERBS = load_words("verbs.txt")


def generate_friend_code() -> str:
    """
    Generate a memorable friend code using common words
    Format: adjective-noun-verb-noun (e.g., "happy-dog-jumps-fence")

    Returns:
        str: A hyphen-separated string of four words
    """
    adjective = secrets.choice(ADJECTIVES)
    noun1 = secrets.choice(NOUNS)
    verb = secrets.choice(VERBS)
    noun2 = secrets.choice(NOUNS)

    # Combine words with hyphens
    return f"{adjective}-{noun1}-{verb}-{noun2}"
