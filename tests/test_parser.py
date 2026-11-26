
from aegis.parser import parse_json_line


def test_valid_limit_event():
    result = parse_json_line(
        '{"type":"LIMIT","id":101,"client":"ALICE",'
        '"side":"BUY","price":100,"qty":5}'
    )

    assert result.valid is True
    assert result.event["type"] == "LIMIT"


def test_invalid_json():
    result = parse_json_line('{"type": LIMIT}')

    assert result.valid is False
    assert result.reject_code == "MALFORMED_EVENT"


def test_non_object_json():
    result = parse_json_line('[1, 2, 3]')

    assert result.valid is False
    assert result.reject_code == "MALFORMED_EVENT"


def test_missing_event_type():
    result = parse_json_line('{"id":101,"client":"ALICE"}')

    assert result.valid is False
    assert result.reject_code == "MALFORMED_EVENT"


def test_duplicate_json_keys():
    result = parse_json_line(
        '{"type":"LIMIT","id":101,"id":102}'
    )

    assert result.valid is False
    assert result.reject_code == "MALFORMED_EVENT"


def test_empty_line():
    result = parse_json_line("")

    assert result.valid is False
    assert result.reject_code == "MALFORMED_EVENT"


def test_unknown_event_type():
    result = parse_json_line(
        '{"type":"UNKNOWN","id":101,"client":"ALICE"}'
    )

    assert result.reject_code == "INVALID_TYPE"


def test_extra_field():
    result = parse_json_line(
        '{"type":"CANCEL","id":101,"client":"ALICE","extra":1}'
    )

    assert result.reject_code == "MALFORMED_EVENT"


def test_invalid_client():
    result = parse_json_line(
        '{"type":"CANCEL","id":101,"client":"ALICE!"}'
    )

    assert result.reject_code == "INVALID_CLIENT"


def test_boolean_id_rejected():
    result = parse_json_line(
        '{"type":"CANCEL","id":true,"client":"ALICE"}'
    )

    assert result.reject_code == "INVALID_ID"


def test_decimal_price_rejected():
    result = parse_json_line(
        '{"type":"LIMIT","id":101,"client":"ALICE",'
        '"side":"BUY","price":100.0,"qty":5}'
    )

    assert result.reject_code == "INVALID_PRICE"


def test_invalid_side():
    result = parse_json_line(
        '{"type":"LIMIT","id":101,"client":"ALICE",'
        '"side":"HOLD","price":100,"qty":5}'
    )

    assert result.reject_code == "INVALID_SIDE"


def test_invalid_quantity():
    result = parse_json_line(
        '{"type":"MARKET","id":101,"client":"ALICE",'
        '"side":"BUY","qty":0}'
    )

    assert result.reject_code == "INVALID_QUANTITY"
