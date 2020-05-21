import io
import os
from typing import NoReturn
from unittest import TestCase
from mapadroid.db.DbFactory import DbFactory
from mapadroid.utils.logging import initLogging
from mapadroid.mad_apk import get_storage_obj, APK_Arch, APK_Type, PackageImporter, MAD_Package, MAD_Packages, \
    MAD_APKS, get_apk_status, file_generator
from mapadroid.utils.walkerArgs import parseArgs


args = parseArgs()
initLogging(args)


class StorageBase(TestCase):
    filepath_rgc = 'APK/RemoteGpsController.apk'
    mimetype = 'application/vnd.android.package-archive'
    cleanup_tables = ['mad_apk_autosearch', 'mad_apks']

    def setUp(self):
        self.storage_init()
        self.db_wrapper, self.db_pool_manager = DbFactory.get_wrapper(args)
        if self.storage_type == 'fs':
            args.sdb = False
        else:
            args.sdb = True
        (self.storage_manager, self.storage_elem) = get_storage_obj(args, self.db_wrapper)
        self.db_purge()

    def tearDown(self):
        self.db_purge()
        self.storage_cleanup()
        self.storage_elem.delete_file(APK_Type.rgc, APK_Arch.noarch)
        self.storage_manager.shutdown()
        self.db_pool_manager.shutdown()

    def storage_cleanup(self):
        pass

    def storage_init(self):
        pass

    def db_purge(self):
        for table in self.cleanup_tables:
            self.db_wrapper.execute('DELETE FROM `%s`' % (table,), commit=True)

    def get_rgc_bytes(self) -> io.BytesIO:
        data = io.BytesIO()
        with open(StorageBase.filepath_rgc, 'rb') as fh:
            data.write(fh.read())
        return data

    def upload_rgc(self, version: str = None) -> NoReturn:
        data = self.get_rgc_bytes()
        if version is None:
            PackageImporter(APK_Type.rgc, APK_Arch.noarch, self.storage_elem, data, StorageBase.mimetype)
        else:
            self.storage_elem.save_file(APK_Type.rgc, APK_Arch.noarch, version, StorageBase.mimetype, data)

    def status_check(self):
        all_data = get_apk_status(self.storage_elem)
        self.assertIsInstance(all_data, MAD_APKS)
        self.assertTrue(APK_Type.pogo in all_data)
        self.assertTrue(APK_Arch.armeabi_v7a in all_data[APK_Type.pogo])
        self.assertTrue(APK_Arch.arm64_v8a in all_data[APK_Type.pogo])
        self.assertFalse(APK_Arch.noarch in all_data[APK_Type.pogo])
        self.assertTrue(APK_Type.rgc in all_data)
        self.assertFalse(APK_Arch.armeabi_v7a in all_data[APK_Type.rgc])
        self.assertFalse(APK_Arch.arm64_v8a in all_data[APK_Type.rgc])
        self.assertTrue(APK_Arch.noarch in all_data[APK_Type.rgc])
        self.assertTrue(APK_Type.pd in all_data)
        self.assertFalse(APK_Arch.armeabi_v7a in all_data[APK_Type.pd])
        self.assertFalse(APK_Arch.arm64_v8a in all_data[APK_Type.pd])
        self.assertTrue(APK_Arch.noarch in all_data[APK_Type.pd])

    def upload_check(self):
        self.assertIsNone(self.storage_elem.get_current_package_info(APK_Type.rgc))
        self.upload_rgc()
        packages_data: MAD_Packages = self.storage_elem.get_current_package_info(APK_Type.rgc)
        self.assertIsInstance(packages_data, MAD_Packages)
        self.assertTrue(APK_Arch.noarch in packages_data)
        package: MAD_Package = packages_data[APK_Arch.noarch]
        self.assertIsInstance(package, MAD_Package)
        self.assertIsNone(package.file_id)
        self.assertIsNotNone(package.filename)
        self.assertTrue(package.mimetype == StorageBase.mimetype)
        self.assertTrue(package.size == os.stat(StorageBase.filepath_rgc).st_size)
        package_data = package.get_package()
        self.assertIsInstance(package_data['arch_disp'], APK_Arch)
        self.assertIsInstance(package_data['usage_disp'], APK_Type)
        package_data = package.get_package(backend=False)
        self.assertIsInstance(package_data['arch_disp'], str)
        self.assertIsInstance(package_data['usage_disp'], str)

    def download_check(self):
        self.upload_rgc()
        gen = file_generator(self.db_wrapper, self.storage_elem, APK_Type.rgc, APK_Arch.noarch)
        data = io.BytesIO()
        for chunk in gen:
            data.write(chunk)
        self.assertTrue(data.getbuffer().nbytes == os.stat(StorageBase.filepath_rgc).st_size)

    def delete_check(self):
        self.upload_rgc()
        self.assertTrue(self.storage_elem.delete_file(APK_Type.rgc, APK_Arch.noarch))
        self.assertIsNone(self.storage_elem.get_current_package_info(APK_Type.rgc))

    def package_upgrade_check(self, version: str):
        self.upload_rgc(version)
        self.upload_rgc()

    def version_check(self):
        version = '0.1'
        self.upload_rgc(version)
        self.assertTrue(self.storage_elem.get_current_version(APK_Type.rgc, APK_Arch.noarch) == version)
