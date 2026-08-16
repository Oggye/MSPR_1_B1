from .build_dataset import main as build_dataset


def run():
    print("STEP 0 — construction datasets multi-horizon")
    build_dataset()
    print("Datasets multi-horizon prêts")


if __name__ == "__main__":
    run()
