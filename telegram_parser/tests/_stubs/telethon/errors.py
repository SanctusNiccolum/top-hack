class FloodWaitError(Exception):
    def __init__(self, seconds=0, **kwargs):
        self.seconds = seconds
        super().__init__(f"flood wait {seconds}s")
