    def set_overlay_max_message_length(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_overlay_max_message_length(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_overlay_max_message_length(self)
        finally:
            self.sesslock.release()

    def set_download_help_dir(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_download_help_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_download_help_dir(self)
        finally:
            self.sesslock.release()

    def set_bartercast(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_bartercast(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_bartercast(self)
        finally:
            self.sesslock.release()

    def set_superpeer_file(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_superpeer_file(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_superpeer_file(self)
        finally:
            self.sesslock.release()

    def set_buddycast_collecting_solution(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_buddycast_collecting_solution(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_buddycast_collecting_solution(self)
        finally:
            self.sesslock.release()

    def set_peer_icon_path(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_peer_icon_path(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_peer_icon_path(self)
        finally:
            self.sesslock.release()

    def set_stop_collecting_threshold(self,value):
        raise OperationNotPossibleAtRuntimeException()

    def get_stop_collecting_threshold(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_stop_collecting_threshold(self)
        finally:
            self.sesslock.release()

