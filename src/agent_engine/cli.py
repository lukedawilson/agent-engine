import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-engine",
        description="Run an OpenHands agent pipeline defined in YAML.",
    )
    parser.parse_args()
