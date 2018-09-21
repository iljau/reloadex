class LaunchParams:
    def __init__(self, working_directory, target_fn_str, file_triggers_reload_fn):
        self.working_directory = working_directory
        self.target_fn_str = target_fn_str
        self.file_triggers_reload_fn = file_triggers_reload_fn

