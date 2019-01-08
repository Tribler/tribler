# Message types for different requests & response
MSG_SUBSCRIBE = 1
MSG_SUBSCRIPTION = 2
MSG_TORRENT_HEALTH_RESPONSE = 3

MAX_SUBSCRIBERS = 10
MAX_PUBLISHERS = 10
PUBLISH_INTERVAL = 5

# Maximum packet payload size in bytes
MAX_PACKET_PAYLOAD_SIZE = 500

# Error definitions
ERROR_UNKNOWN_PEER = "Unknown peer! No response sent"
ERROR_UNKNOWN_RESPONSE = "Received response from non-subscribed peer. Dropping it."
ERROR_NO_CONTENT = "Nothing to publish"
