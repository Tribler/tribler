from tribler.core.components.database.db.store import HealthItemsPayload


def test_unpack_health_items():
    data = HealthItemsPayload(b';;1,2,3;;4,5,6,foo,bar;7,8,9,baz;;ignored data').serialize()
    items = HealthItemsPayload.unpack(data)
    assert items == [
        (0, 0, 0),
        (0, 0, 0),
        (1, 2, 3),
        (0, 0, 0),
        (4, 5, 6),
        (7, 8, 9),
        (0, 0, 0),
    ]


def test_parse_health_data_item():
    item = HealthItemsPayload.parse_health_data_item(b'')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'invalid item')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,2,3')
    assert item == (1, 2, 3)

    item = HealthItemsPayload.parse_health_data_item(b'-1,2,3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,-2,3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,2,-3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'100,200,300')
    assert item == (100, 200, 300)

    item = HealthItemsPayload.parse_health_data_item(b'2,3,4,5,6,7')
    assert item == (2, 3, 4)

    item = HealthItemsPayload.parse_health_data_item(b'3,4,5,some arbitrary,data,foo,,bar')
    assert item == (3, 4, 5)
