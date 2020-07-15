from flask import Response
import io
import os
from unittest import TestCase
from mapadroid.db.DbFactory import DbFactory
from mapadroid.tests.test_utils import upload_rgc, mimetype, filepath_rgc
from mapadroid.utils.logging import init_logging
from mapadroid.mad_apk import get_storage_obj, APKArch, APKType, MADPackage, MADPackages, MADapks, get_apk_status,\
    file_generator
from mapadroid.utils.walkerArgs import parse_args


args = parse_args()
init_logging(args)


class StorageBase(TestCase):
    cleanup_tables = ['mad_apk_autosearch', 'mad_apks']

    def setUp(self):
        self.storage_init()
        self.db_wrapper, self.db_pool_manager = DbFactory.get_wrapper(args)
        try:
            storage_type = self.storage_type
        except AttributeError:
            storage_type = 'fs'
        if storage_type == 'fs':
            args.apk_storage_interface = 'fs'
        else:
            args.apk_storage_interface = 'db'
        (self.storage_manager, self.storage_elem) = get_storage_obj(args, self.db_wrapper)
        self.db_purge()
        self.storage_elem.delete_file(APKType.rgc, APKArch.noarch)

    def tearDown(self):
        self.db_purge()
        self.storage_cleanup()
        self.storage_elem.delete_file(APKType.rgc, APKArch.noarch)
        self.storage_manager.shutdown()
        self.db_pool_manager.shutdown()

    def storage_cleanup(self):
        pass

    def storage_init(self):
        pass

    def db_purge(self):
        for table in self.cleanup_tables:
            self.db_wrapper.execute('DELETE FROM `%s`' % (table,), commit=True)

    def status_check(self):
        all_data = get_apk_status(self.storage_elem)
        self.assertIsInstance(all_data, MADapks)
        self.assertTrue(APKType.pogo in all_data)
        self.assertTrue(APKArch.armeabi_v7a in all_data[APKType.pogo])
        self.assertTrue(APKArch.arm64_v8a in all_data[APKType.pogo])
        self.assertFalse(APKArch.noarch in all_data[APKType.pogo])
        self.assertTrue(APKType.rgc in all_data)
        self.assertFalse(APKArch.armeabi_v7a in all_data[APKType.rgc])
        self.assertFalse(APKArch.arm64_v8a in all_data[APKType.rgc])
        self.assertTrue(APKArch.noarch in all_data[APKType.rgc])
        self.assertTrue(APKType.pd in all_data)
        self.assertFalse(APKArch.armeabi_v7a in all_data[APKType.pd])
        self.assertFalse(APKArch.arm64_v8a in all_data[APKType.pd])
        self.assertTrue(APKArch.noarch in all_data[APKType.pd])

    def upload_check(self):
        self.assertIsNone(self.storage_elem.get_current_package_info(APKType.rgc))
        upload_rgc(self.storage_elem)
        packages_data: MADPackages = self.storage_elem.get_current_package_info(APKType.rgc)
        self.assertIsInstance(packages_data, MADPackages)
        self.assertTrue(APKArch.noarch in packages_data)
        package: MADPackage = packages_data[APKArch.noarch]
        self.assertIsInstance(package, MADPackage)
        self.assertIsNone(package.file_id)
        self.assertIsNotNone(package.filename)
        self.assertTrue(package.mimetype == mimetype)
        self.assertTrue(package.size == os.stat(filepath_rgc).st_size)
        package_data = package.get_package()
        self.assertIsInstance(package_data['arch_disp'], APKArch)
        self.assertIsInstance(package_data['usage_disp'], APKType)
        package_data = package.get_package(backend=False)
        self.assertIsInstance(package_data['arch_disp'], str)
        self.assertIsInstance(package_data['usage_disp'], str)

    def download_check(self):
        upload_rgc(self.storage_elem)
        gen = file_generator(self.db_wrapper, self.storage_elem, APKType.rgc, APKArch.noarch)
        data = io.BytesIO()
        for chunk in gen:
            data.write(chunk)
        self.assertTrue(data.getbuffer().nbytes == os.stat(filepath_rgc).st_size)

    def delete_check(self):
        upload_rgc(self.storage_elem)
        self.assertTrue(self.storage_elem.delete_file(APKType.rgc, APKArch.noarch))
        self.assertIsNone(self.storage_elem.get_current_package_info(APKType.rgc))

    def package_upgrade_check(self, version: str):
        upload_rgc(self.storage_elem, version=version)
        upload_rgc(self.storage_elem)

    def version_check(self):
        version = '0.1'
        upload_rgc(self.storage_elem, version=version)
        self.assertTrue(self.storage_elem.get_current_version(APKType.rgc, APKArch.noarch) == version)

    def test_check_invalid(self):
        gen = file_generator(self.db_wrapper, self.storage_elem, APKType.rgc, APKArch.noarch)
        self.assertTrue(isinstance(gen, Response))
        self.assertTrue(gen.status_code == 404)
