[download_defaults]
hops = integer(default=0)
selected_files = string_list(default=list())
selected_file_indexes = int_list(default=list())
safe_seeding = boolean(default=False)
user_stopped = boolean(default=False)
share_mode = boolean(default=False)
upload_mode = boolean(default=False)
time_added = integer(default=0)
bootstrap_download = boolean(default=False)
channel_download = boolean(default=False)
add_download_to_channel = boolean(default=False)
saveas = string(default=None)

[state]
metainfo = string(default='ZGU=')
engineresumedata = string(default='ZGU=')
