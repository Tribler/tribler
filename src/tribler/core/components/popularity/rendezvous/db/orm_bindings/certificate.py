from pony.orm import Required, db_session


def define_binding(db):
    class RendezvousCertificate(db.Entity):
        public_key = Required(bytes, index=True)
        counter = Required(int)

    return RendezvousCertificate
