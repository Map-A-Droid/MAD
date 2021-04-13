import mock
import pytest
import responses
from apksearch.entities import PackageBase, PackageVariant, PackageVersion

from mapadroid.mad_apk import utils, wizard
from mapadroid.mad_apk.apk_enums import APKArch
from mapadroid.utils.global_variables import VERSIONCODES_URL

mock_versions = """{"0.123.0_32": 1, "0.123.1_32": 3, "0.123.1_64": 4}"""
mock_json_resp = {"0.123.0_32": 1, "0.123.1_32": 3, "0.123.1_64": 4}


@pytest.mark.parametrize(
    "file_resp,gh_resp,arch,version,supported", [
        (mock_versions, "{}", APKArch.armeabi_v7a, "0.123.0", True),
        (mock_versions, "{}", APKArch.arm64_v8a, "0.123.0", False),
        (mock_versions, "{}", APKArch.armeabi_v7a, "0.123.1", True),
        (mock_versions, "{}", APKArch.arm64_v8a, "0.123.1", True),
        ("{}", mock_versions, APKArch.armeabi_v7a, "0.123.0", True),
        ("{}", mock_versions, APKArch.arm64_v8a, "0.123.0", False),
        ("{}", mock_versions, APKArch.armeabi_v7a, "0.123.1", True),
        ("{}", mock_versions, APKArch.arm64_v8a, "0.123.1", True),
    ])
@responses.activate
def test_supported_pogo_version(file_resp, gh_resp, arch, version, supported):
    with mock.patch("mapadroid.utils.functions.open", new_callable=mock.mock_open, read_data=file_resp):
        responses.add(
            responses.GET,
            url=VERSIONCODES_URL,
            body=gh_resp
        )
        assert utils.supported_pogo_version(arch, version) == supported
        if gh_resp == "{}" and supported:
            assert len(responses.calls) == 0
        else:
            assert len(responses.calls) == 1


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
supported_a = """{"0.123.0_32": 1}"""
supported_b = """{"0.123.0_32": 1, "0.123.1_32": 3, "0.123.1_64": 4}"""


@pytest.mark.parametrize("avail_versions,arch,exp_ver,package,file_resp", [
    (pkg_version, APKArch.armeabi_v7a, "0.123.0", var_a, supported_a),
    (pkg_version, APKArch.arm64_v8a, None, None, supported_a),
    (pkg_version, APKArch.armeabi_v7a, "0.123.1", var_b, supported_b),
    (pkg_version, APKArch.arm64_v8a, "0.123.1", var_c, supported_b)
])
def test_get_latest_supported(avail_versions, arch, exp_ver, package, file_resp):
    with mock.patch("mapadroid.utils.functions.open", new_callable=mock.mock_open, read_data=file_resp):
        assert wizard.APKWizard.get_latest_supported(arch, avail_versions) == (exp_ver, package)


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
