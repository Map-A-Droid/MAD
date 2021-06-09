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
    app.router.add_view('/devicecontrol', DevicecontrolEndpoint)
    app.router.add_view('/take_screenshot', TakeScreenshotEndpoint)
    app.router.add_view('/click_screenshot', ClickScreenshotEndpoint)
    app.router.add_view('/swipe_screenshot', SwipeScreenshotEndpoint)
    app.router.add_view('/quit_pogo', QuitPogoEndpoint)
    app.router.add_view('/restart_phone', RestartPhoneEndpoint)
    app.router.add_view('/clear_game_data', ClearGameDataEndpoint)
    app.router.add_view('/download_logcat', DownloadLogcatEndpoint)
    app.router.add_view('/send_gps', SendGpsEndpoint)
    app.router.add_view('/send_text', SendTextEndpoint)
    app.router.add_view('/upload', UploadEndpoint)
    app.router.add_view('/send_command', SendCommandEndpoint)
    app.router.add_view('/get_uploaded_files', GetUploadedFilesEndpoint)
    app.router.add_view('/uploaded_files', UploadedFilesEndpoint)
    app.router.add_view('/delete_file', DeleteFileEndpoint)
    app.router.add_view('/install_file', InstallFileEndpoint)
    app.router.add_view('/get_install_log', GetInstallLogEndpoint)
    app.router.add_view('/delete_log_entry', DeleteLogEntryEndpoint)
    app.router.add_view('/install_status', InstallStatusEndpoint)
    app.router.add_view('/install_file_all_devices', InstallFileAllDevicesEndpoint)
    app.router.add_view('/restart_job', RestartJobEndpoint)
    app.router.add_view('/delete_log', DeleteLogEndpoint)
    app.router.add_view('/get_all_workers', GetAllWorkersEndpoint)
    app.router.add_view('/job_for_worker', JobForWorkerEndpoint)
    app.router.add_view('/reload_jobs', ReloadJobsEndpoint)
