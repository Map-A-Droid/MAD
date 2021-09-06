import json

import mock
import pytest
import responses
from apksearch.entities import PackageBase, PackageVariant, PackageVersion

from mapadroid.mad_apk import utils, wizard
from mapadroid.mad_apk.apk_enums import APKArch
from mapadroid.utils.global_variables import BACKEND_SUPPORTED_VERSIONS

mock_versions = {
    "32": [
        "0.123.0",
        "0.123.1",
    ],
    "64": [
        "0.123.1",
    ]
}
mock_versions_limited = {
    "32": [
        "0.123.0",
    ],
    "64": []
}
mock_versions_json = json.dumps(mock_versions)


@pytest.mark.parametrize(
    "response_body,response_code,token,expected,err", [
        (None, 500, None, None, ValueError),
        (None, 403, "CoolToken", None, ConnectionError),
        (None, 500, "CoolToken", None, ConnectionError),
        (mock_versions_json[0:-2], 200, "CoolToken", None, ValueError),
        (mock_versions_json, 200, "CoolToken", mock_versions, None),
    ])
@responses.activate
def test_get_backend_versions(response_body, response_code, token, expected, err):
    responses.add(
        responses.GET,
        url=BACKEND_SUPPORTED_VERSIONS,
        body=response_body,
        status=response_code
    )
    if not err:
        assert utils.get_backend_versions(token) == expected
    else:
        with pytest.raises(err):
            utils.get_backend_versions(token)


mock_versions = {
    "32": [
        "0.123.0",
        "0.123.1",
    ],
    "64": [
        "0.123.1",
    ]
}
file_resp_limited = {"0.123.0_32": 1}
file_resp_full = {"0.123.0_32": 1, "0.123.1_32": 2, "0.123.1_64": 3}


@pytest.mark.parametrize(
    "file_resp,expected", [
        (json.dumps(file_resp_limited), mock_versions_limited),
        (json.dumps(file_resp_full), mock_versions),
    ]
)
def test_get_local_versions(file_resp, expected):
    with mock.patch("mapadroid.utils.functions.open", new_callable=mock.mock_open, read_data=file_resp):
        assert utils.get_local_versions() == expected


@pytest.mark.parametrize(
    "supported_versions,arch,version,is_supported", [
        (mock_versions, APKArch.armeabi_v7a, "0.123.0", True),
        (mock_versions, APKArch.arm64_v8a, "0.123.0", False),
        (mock_versions, APKArch.armeabi_v7a, "0.123.1", True),
        (mock_versions, APKArch.arm64_v8a, "0.123.1", True),
    ])
@responses.activate
def test_supported_pogo_version(supported_versions, arch, version, is_supported, mocker):
    mocker.patch("mapadroid.mad_apk.utils.get_backend_versions", return_value=supported_versions)
    assert utils.supported_pogo_version(arch, version, "SomeToken") == is_supported


var_a = PackageVariant("APK", "nodpi", 1)
var_a_a = PackageVariant("BUNDLE", "nodpi", 11)
var_b = PackageVariant("APK", "nodpi", 3)
var_c = PackageVariant("APK", "nodpi", 4)
pkg_version = PackageBase("Pokemon GO", "ffff", versions={
    "0.123.0": PackageVersion(
        "nolinky",
        arch_data={
            "armeabi-v7a": [var_a, var_a_a]
        }
    ),
    "0.123.1": PackageVersion(
        "nolinky",
        arch_data={
            "armeabi-v7a": [var_b],
            "arm64-v8a": [var_c]
        }
    )
})


@pytest.mark.parametrize("avail_versions,supported_ver,arch,exp_ver,package", [
    (pkg_version, mock_versions_limited, APKArch.armeabi_v7a, "0.123.0", var_a),
    (pkg_version, mock_versions_limited, APKArch.arm64_v8a, None, None),
    (pkg_version, mock_versions, APKArch.armeabi_v7a, "0.123.1", var_b),
    (pkg_version, mock_versions, APKArch.arm64_v8a, "0.123.1", var_c)
])
def test_get_latest_supported(avail_versions, supported_ver, arch, exp_ver, package, mocker):
    mocker.patch("mapadroid.mad_apk.utils.get_backend_versions", return_value=supported_ver)
    assert wizard.APKWizard.get_latest_supported(arch, avail_versions, "Token") == (exp_ver, package)


@pytest.mark.parametrize("gls_v,sto_v,lvc_v,arch,msg", [
    (("0.123.0", var_a), "0.122.0", 0, APKArch.armeabi_v7a, "Newer version found"),
    (("0.123.0", var_a), "0.123.0", 1, APKArch.armeabi_v7a, "Already have the latest version"),
    (("0.123.0", var_a), "0.123.0", 10, APKArch.armeabi_v7a, "Unable to find a supported version")
])
@mock.patch("mapadroid.mad_apk.wizard.get_available_versions")
@mock.patch("mapadroid.mad_apk.wizard.APKWizard.get_latest_supported")
@mock.patch("mapadroid.mad_apk.wizard.APKWizard.lookup_version_code")
def tests_find_latest_pogo(lvc, gls, gav, gls_v, sto_v, lvc_v, arch, msg, caplog, wiz_instance):
    gav.return_value = None
    gls.return_value = gls_v
    lvc.return_value = lvc_v
    wiz_instance.storage.get_current_version.return_value = sto_v
    results = wiz_instance.find_latest_pogo(arch)
    assert results == ("0.123.0", var_a)
    assert msg in caplog.text


@mock.patch("mapadroid.mad_apk.wizard.package_search")
def test_ensure_cache_for_download(psearch):
    wizard.get_available_versions.cache_clear()
    wizard.get_available_versions()
    wizard.get_available_versions()
    psearch.assert_called_once()


@mock.patch("mapadroid.mad_apk.wizard.package_search")
def test_parsing_error(psearch, caplog):
    wizard.get_available_versions.cache_clear()
    psearch.side_effect = mock.Mock(side_effect=IndexError)
    wizard.get_available_versions()
    assert "Unable to query APKMirror" in caplog.text
