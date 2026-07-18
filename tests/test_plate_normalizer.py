from app.recognizer.plate_text import build_plate_candidates, normalize_plate


def test_normalize_blue_plate():
    assert normalize_plate("苏 A·8K2N6") == "苏A8K2N6"


def test_normalize_new_energy_plate():
    assert normalize_plate("粤B 12345D") == "粤B12345D"


def test_normalize_returns_none_for_non_plate_text():
    assert normalize_plate("停车场入口") is None


def test_normalize_wj_special_plate():
    assert normalize_plate("WJ·N22628") == "WJN22628"


def test_normalize_common_special_plate_types():
    cases = {
        "粤A1234学": "粤A1234学",
        "粤A12345学": "粤A12345学",
        "粤A1234警": "粤A1234警",
        "粤A1234挂": "粤A1234挂",
        "粤A1234试": "粤A1234试",
        "粤Z1234港": "粤Z1234港",
        "粤Z12345港": "粤Z12345港",
        "粤Z1234澳": "粤Z1234澳",
        "使12345": "使12345",
        "领123456": "领123456",
        "军A12345": "军A12345",
    }
    for raw_text, expected in cases.items():
        assert normalize_plate(raw_text) == expected


def test_build_double_line_motorcycle_plate():
    candidates = build_plate_candidates([
        ("川·A", 0.996),
        ("4X144", 0.979),
    ])

    assert candidates[-1].plate_number == "川A4X144"
    assert candidates[-1].confidence == 0.979
