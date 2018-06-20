
def create_channel(public_key, private_key, title, md_list):
    torrent = create_channel_torrent(public_key, title, md_list)
    torrentDB.add(torrent.infohash, torrent)
    md = create_channel_md(
            publisher = public_key,
            sign      = private_key,
            infohash  = torrent.infohash, 
            date      = datetime.now(),
            title     = title)
    DB.metadata.add(md)
    


def create_channel_torrent(dirname, title, md_list):
    create_dir(dirname)
    for i,md in enumerate(md_list):
        create_file(name=dirname+str(i), contents=md.serialized())
    torrent = create_torrent(dirname)
    return torrent


def join_channel(PK):
    channel_dir = fetch_channel(ChannelORM)
    consume_contents(channel_dir)


def fetch_channel(ChannelORM):
    libtorrent_download(ChannelORM.infohash)


def consume_contents(dirname):
    # Metadata is only added if its timestamp is newer than
    # the timestamp of the channel in DB.
    # We can later add skip on file numbers for efficiency
    # of making updates.
    for f in sorted(files(dirname)):
        process_metadata_package(read_file(f))

def unpack_gossip(gsp_ser):
    try:
        sig, PK, tc_pointer, timestamp, md_ser =
        deserialize_gossip(gsp_ser)
    except:
        process_deserialize_error(err)
        return

    if not gossip_signature_OK(gsp_ser):
        # Possibly decrease the sender's trust rating?
        return

    if known(sig):
        # We already have this package.
        return

    if timestamp < channel(PK).timestamp:
        # This is a package from the older version of this channel.
        # It was deleted in some earlier update. We don't want it.
        return

    # If PK is unknown, we:
    #  *first* wait until all necessary
    #   procedures to add it are completed (e.g. asking friends, etc.)
    #  *then* check if it is trusted or not. This is more
    #   robust than just blindly accepting every new PK. 
    if not known(PK):
        process_new_PK(PK, source_channel)

    if not trusted(PK):
        return

    return md_ser

def unpack_metadata(md_ser):
    try:
        md = deserialize_metadata(md_ser)
    except:
        process_deserialize_error(err)
    return md

def process_metadata_package(gsp_ser, allow_delete = False):
    md = unpack_metadata(unpack_gossip(gsp_ser))
    if md.type == MD_DELETE:
        DB.metadata.remove(md.sig)
    else:
        DB.metadata.add(md)

def DB.metadata.add(md):
    # We don't do deduplication of infohashes
    # because different packagers could make different
    # uses of the same torrent.

    mdtype = md.type
    infohash = md.infohash
    size = md.size
    data = md.date
    title = md.title
    terms = stemmer(title)
    tags_parsed = parse(tags)
    terms.extend(tags_parsed.searchable)
    addition_timestamp = channel_update_ts







    

    



            


