import select


def main():
    print("_dummy_app", 143)
    try:
        select.select([], [], [])
    except KeyboardInterrupt as e:
        pass