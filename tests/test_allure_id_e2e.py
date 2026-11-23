"""Report-level checks for marker names and the native Allure label."""

import json

import pytest


@pytest.mark.parametrize("parallel", [False, True], ids=["serial", "xdist"])
@pytest.mark.parametrize(
    "marker",
    ["allure_id_33158", "test_id_33158", 'allure_label("33158", label_type="as_id")'],
)
def test_report_contains_id_for_each_parameter(pytester, marker, parallel):
    pytester.makepyfile(f'''
        import pytest

        @pytest.mark.{marker}
        @pytest.mark.parametrize("value", [1, 2])
        def test_case(value):
            assert value > 0
    ''')
    args = ["--beacon", "--beacon-file-exclude-status="]
    if parallel:
        args.extend(["-n", "2"])
    result = pytester.runpytest_subprocess(*args)
    result.assert_outcomes(passed=2)
    reports = list(pytester.path.glob("beacon_reports/*.json"))
    assert len(reports) == 1
    tests = json.loads(reports[0].read_text())["results"]["tests"]
    assert len(tests) == 2
    assert {test["allureId"] for test in tests} == {33158}


def test_setup_error_keeps_encoded_id(pytester):
    pytester.makepyfile('''
        import pytest

        @pytest.fixture
        def broken():
            raise RuntimeError("setup failed")

        @pytest.mark.test_id_33158
        def test_case(broken):
            pass
    ''')
    result = pytester.runpytest_subprocess("--beacon", "--beacon-file-exclude-status=")
    result.assert_outcomes(errors=1)
    reports = list(pytester.path.glob("beacon_reports/*.json"))
    assert len(reports) == 1
    tests = json.loads(reports[0].read_text())["results"]["tests"]
    assert len(tests) == 1
    assert tests[0]["allureId"] == 33158
