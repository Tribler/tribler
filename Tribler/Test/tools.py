def trial_timeout(timeout):
    def trial_timeout_decorator(func):
        func.timeout = timeout
        return func
    return trial_timeout_decorator
