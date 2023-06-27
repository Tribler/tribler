from pony.orm import Required, db_session


def define_binding(db):
    class RendezvousCertificate(db.Entity):
        public_key = Required(bytes, index=True)
        counter = Required(int)

        @classmethod
        @db_session
        def get_count(cls, pk: bytes) -> int:
            return RendezvousCertificate.get(public_key == pk).count()

    return RendezvousCertificate
