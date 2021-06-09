from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.ClearGameDataEndpoint import ClearGameDataEndpoint
from mapadroid.madmin.endpoints.routes.control.ClickScreenshotEndpoint import ClickScreenshotEndpoint
from mapadroid.madmin.endpoints.routes.control.DeleteFileEndpoint import DeleteFileEndpoint
from mapadroid.madmin.endpoints.routes.control.DeleteLogEndpoint import DeleteLogEndpoint
from mapadroid.madmin.endpoints.routes.control.DeleteLogEntryEndpoint import DeleteLogEntryEndpoint
from mapadroid.madmin.endpoints.routes.control.DevicecontrolEndpoint import DevicecontrolEndpoint
from mapadroid.madmin.endpoints.routes.control.DownloadLogcatEndpoint import DownloadLogcatEndpoint
from mapadroid.madmin.endpoints.routes.control.GetAllWorkersEndpoint import GetAllWorkersEndpoint
from mapadroid.madmin.endpoints.routes.control.GetInstallLogEndpoint import GetInstallLogEndpoint
from mapadroid.madmin.endpoints.routes.control.GetUploadedFilesEndpoint import GetUploadedFilesEndpoint
from mapadroid.madmin.endpoints.routes.control.InstallFileAllDevicesEndpoint import InstallFileAllDevicesEndpoint
from mapadroid.madmin.endpoints.routes.control.InstallFileEndpoint import InstallFileEndpoint
from mapadroid.madmin.endpoints.routes.control.InstallStatusEndpoint import InstallStatusEndpoint
from mapadroid.madmin.endpoints.routes.control.JobForWorkerEndpoint import JobForWorkerEndpoint
from mapadroid.madmin.endpoints.routes.control.QuitPogoEndpoint import QuitPogoEndpoint
from mapadroid.madmin.endpoints.routes.control.ReloadJobsEndpoint import ReloadJobsEndpoint
from mapadroid.madmin.endpoints.routes.control.RestartJobEndpoint import RestartJobEndpoint
from mapadroid.madmin.endpoints.routes.control.RestartPhoneEndpoint import RestartPhoneEndpoint
from mapadroid.madmin.endpoints.routes.control.SendCommandEndpoint import SendCommandEndpoint
from mapadroid.madmin.endpoints.routes.control.SendGpsEndpoint import SendGpsEndpoint
from mapadroid.madmin.endpoints.routes.control.SendTextEndpoint import SendTextEndpoint
from mapadroid.madmin.endpoints.routes.control.SwipeScreenshotEndpoint import SwipeScreenshotEndpoint
from mapadroid.madmin.endpoints.routes.control.TakeScreenshotEndpoint import TakeScreenshotEndpoint
from mapadroid.madmin.endpoints.routes.control.UploadEndpoint import UploadEndpoint
from mapadroid.madmin.endpoints.routes.control.UploadedFilesEndpoint import UploadedFilesEndpoint


def register_routes_control_endpoints(app: web.Application):
    app.router.add_view('/devicecontrol', DevicecontrolEndpoint, name='get_phonescreens')
    app.router.add_view('/take_screenshot', TakeScreenshotEndpoint, name='take_screenshot')
    app.router.add_view('/click_screenshot', ClickScreenshotEndpoint, name='click_screenshot')
    app.router.add_view('/swipe_screenshot', SwipeScreenshotEndpoint, name='swipe_screenshot')
    app.router.add_view('/quit_pogo', QuitPogoEndpoint, name='quit_pogo')
    app.router.add_view('/restart_phone', RestartPhoneEndpoint, name='restart_phone')
    app.router.add_view('/clear_game_data', ClearGameDataEndpoint, name='clear_game_data')
    app.router.add_view('/download_logcat', DownloadLogcatEndpoint, name='get_logcat')
    app.router.add_view('/send_gps', SendGpsEndpoint, name='send_gps')
    app.router.add_view('/send_text', SendTextEndpoint, name='send_text')
    app.router.add_view('/upload', UploadEndpoint, name='upload')
    app.router.add_view('/send_command', SendCommandEndpoint, name='send_command')
    app.router.add_view('/get_uploaded_files', GetUploadedFilesEndpoint, name='get_uploaded_files')
    app.router.add_view('/uploaded_files', UploadedFilesEndpoint, name='uploaded_files')
    app.router.add_view('/delete_file', DeleteFileEndpoint, name='delete_file')
    app.router.add_view('/install_file', InstallFileEndpoint, name='install_file')
    app.router.add_view('/get_install_log', GetInstallLogEndpoint, name='get_install_log')
    app.router.add_view('/delete_log_entry', DeleteLogEntryEndpoint, name='delete_log_entry')
    app.router.add_view('/install_status', InstallStatusEndpoint, name='install_status')
    app.router.add_view('/install_file_all_devices', InstallFileAllDevicesEndpoint, name='install_file_all_devices')
    app.router.add_view('/restart_job', RestartJobEndpoint, name='restart_job')
    app.router.add_view('/delete_log', DeleteLogEndpoint, name='delete_log')
    app.router.add_view('/get_all_workers', GetAllWorkersEndpoint, name='get_all_workers')
    app.router.add_view('/job_for_worker', JobForWorkerEndpoint, name='job_for_worker')
    app.router.add_view('/reload_jobs', ReloadJobsEndpoint, name='reload_jobs')
