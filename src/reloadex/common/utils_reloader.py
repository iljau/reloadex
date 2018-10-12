class LaunchParams:
    def __init__(self, working_directory, argparse_args, file_triggers_reload_fn):
        self.working_directory = working_directory
        self.argparse_args = argparse_args
        self.file_triggers_reload_fn = file_triggers_reload_fn

