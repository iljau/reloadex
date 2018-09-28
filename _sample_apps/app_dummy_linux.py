import select
import atexit

@atexit.register
def app_atexit(*args, **kwargs):
    print("app_atexit", args, kwargs)

def main():
    print("_dummy_app", 125678)
    try:
        select.select([], [], [])
    except KeyboardInterrupt as e:
        print("app_dummy_linux.py KeyboardInterrupt")
        pass

if __name__ == "__main__":
    main()