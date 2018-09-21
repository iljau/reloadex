import itertools
from time import sleep


def main():
    print("_dummy_app", 443)
    try:
        for i in itertools.count():
            sleep(60)
    except KeyboardInterrupt as e:
        pass