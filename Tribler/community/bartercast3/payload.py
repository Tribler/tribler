from Tribler.dispersy.payload import Payload


class BarterRecordPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self,
                     meta,
                     upload_first_to_second,
                     upload_second_to_first,
                     # the following debug values are all according to first_member
                     first_timestamp,
                     first_upload,
                     first_download,
                     first_total_up,
                     first_total_down,
                     # the following debug values are all according to second_member
                     second_timestamp,
                     second_upload,
                     second_download,
                     second_total_up,
                     second_total_down):

            assert isinstance(upload_first_to_second, (int, long))
            assert isinstance(upload_second_to_first, (int, long))
            assert isinstance(first_timestamp, float)
            assert isinstance(first_upload, (int, long))
            assert isinstance(first_download, (int, long))
            assert isinstance(first_total_up, (int, long))
            assert isinstance(first_total_down, (int, long))
            assert isinstance(second_timestamp, float)
            assert isinstance(second_upload, (int, long))
            assert isinstance(second_download, (int, long))
            assert isinstance(second_total_up, (int, long))
            assert isinstance(second_total_down, (int, long))

            super(BarterRecordPayload.Implementation, self).__init__(meta)
            self.upload_first_to_second = upload_first_to_second
            self.upload_second_to_first = upload_second_to_first
            # the following debug values are all according to first_member
            self.first_timestamp = first_timestamp
            self.first_upload = first_upload
            self.first_download = first_download
            self.first_total_up = first_total_up
            self.first_total_down = first_total_down
            # the following debug values are all according to second_member
            self.second_timestamp = second_timestamp
            self.second_upload = second_upload
            self.second_download = second_download
            self.second_total_up = second_total_up
            self.second_total_down = second_total_down
