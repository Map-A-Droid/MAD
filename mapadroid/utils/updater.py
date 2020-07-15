import glob
import json
import os
import re
import time
from datetime import datetime, timedelta
from enum import Enum
from multiprocessing import Queue, Event
from queue import Empty
from threading import RLock, Thread
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.mad_apk import AbstractAPKStorage, is_newer_version, APKType, file_generator, lookup_arch_enum, \
    APKPackage, APKArch, supported_pogo_version, MADPackages


logger = get_logger(LoggerEnums.utils)


class JobType(Enum):
    INSTALLATION = 0
    REBOOT = 1
    RESTART = 2
    STOP = 3
    PASSTHROUGH = 4
    START = 5
    SMART_UPDATE = 6
    CHAIN = 99


class JobReturn(Enum):
    UNKNOWN = 0
    SUCCESS = 1
    NOCONNECT = 2
    FAILURE = 3
    TERMINATED = 4
    NOT_REQUIRED = 5
    NOT_SUPPORTED = 6


SUCCESS_STATES = [JobReturn.SUCCESS, JobReturn.NOT_REQUIRED, JobReturn.NOT_SUPPORTED]


class DeviceUpdater(object):
    def __init__(self, websocket, args, returning, db, storage_obj: AbstractAPKStorage):
        self._websocket = websocket
        self._update_queue = Queue()
        self._update_mutex = RLock()
        self._db = db
        self._storage_obj = storage_obj
        self._log = {}
        self._args = args
        self._commands: dict = {}
        self._globaljoblog: dict = {}
        self._current_job_id = []
        self._current_job_device = []
        self._returning = returning
        self.storage_obj: AbstractAPKStorage = storage_obj
        try:
            if os.path.exists('update_log.json'):
                with open('update_log.json') as logfile:
                    self._log = json.load(logfile)
        except json.decoder.JSONDecodeError:
            logger.error('Corrupted update_log.json file found. Deleting the file. Please check remaining disk space '
                         'or disk health.')
            os.remove('update_log.json')

        self.init_jobs()
        self.kill_old_jobs()
        self.load_automatic_jobs()

        self._stop_updater_threads: Event = Event()
        self.t_updater = []
        for i in range(self._args.job_thread_count):
            job_thread = Thread(name='apk_updater-{}'.format(str(i)), target=self.process_update_queue, args=(i,))
            job_thread.daemon = True
            self.t_updater.append(job_thread)
            job_thread.start()

    def stop_updater(self):
        self._stop_updater_threads.set()
        for thread in self.t_updater:
            thread.join()

    def init_jobs(self):
        self._commands = {}
        if os.path.exists('commands.json'):
            with open('commands.json') as cmdfile:
                self._commands = json.loads(cmdfile.read())

        # load personal commands

        for command_file in glob.glob(os.path.join("personal_commands", "*.json")):
            try:
                with open(command_file) as personal_command:
                    peronal_cmd = json.loads(personal_command.read())
                for command in peronal_cmd:
                    if command in self._commands:
                        logger.error("Command {} already exist - skipping", command)
                    else:
                        logger.info('Loading personal command: {}', command)
                        self._commands[command] = peronal_cmd[command]
            except Exception as e:
                logger.error('Cannot add job {} - Reason: {}', command_file, e)

    def return_commands(self):
        return self._commands

    @logger.catch()
    def restart_job(self, job_id: int):
        if (job_id) in self._log:
            origin = self._log[job_id]['origin']
            file_ = self._log[job_id]['file']
            jobtype = self._log[job_id]['jobtype']
            globalid = self._log[job_id]['globalid']
            redo = self._log[job_id].get('redo', False)
            waittime = self._log[job_id].get('waittime', 0)
            jobname = self._log[job_id].get('redo', None)

            if globalid not in self._globaljoblog:
                self._globaljoblog[globalid] = {}
                self._globaljoblog[globalid]['laststatus'] = None
                self._globaljoblog[globalid]['lastjobend'] = None

            if redo:
                algo = self.get_job_algo_value(algotyp=self._globaljoblog[globalid].get('algotype',
                                                                                        'flex'),
                                               algovalue=self._globaljoblog[globalid].get('algovalue',
                                                                                          0)) + waittime

                processtime = datetime.timestamp(datetime.now() + timedelta(minutes=algo))

                self.write_status_log(str(job_id), field='processingdate', value=processtime)
                self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                             counter=0,
                             status='future', waittime=waittime, processtime=processtime, redo=redo,
                             jobname=jobname)

            else:
                self.write_status_log(str(job_id), field='processingdate', delete=True)
                self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                             status='requeued',
                             jobname=jobname)

        return True

    def kill_old_jobs(self):
        logger.info("Checking for outdated jobs")
        for job in self._log.copy():
            if self._log[job]['status'] in (
                    'pending', 'starting', 'processing', 'not connected', 'future', 'not required') \
                    and not self._log[job].get('auto', False):
                logger.debug("Cancel job {} - it is outdated", job)
                self.write_status_log(str(job), field='status', value='cancelled')
            elif self._log[job].get('auto', False):
                self.write_status_log(str(job), delete=True)

    @logger.catch()
    def process_update_queue(self, threadnumber):
        logger.info("Starting device job processor thread No {}", threadnumber)
        time.sleep(10)
        while not self._stop_updater_threads.is_set():
            try:
                jobstatus = JobReturn.UNKNOWN
                try:
                    # item = self._update_queue.get()
                    item = self._update_queue.get_nowait()
                except Empty:
                    time.sleep(1)
                    continue
                if item is None:
                    time.sleep(1)
                    continue

                if item not in self._log:
                    continue

                job_id = item
                origin = self._log[str(job_id)]['origin']

                self._update_mutex.acquire()
                try:
                    if origin in self._current_job_device:
                        self._update_queue.put(str(job_id))
                        continue

                    self._current_job_device.append(origin)
                finally:
                    self._update_mutex.release()

                file_ = self._log[str(job_id)]['file']
                counter = self._log[str(job_id)]['counter']
                jobtype = self._log[str(job_id)]['jobtype']
                waittime = self._log[str(job_id)].get('waittime', 0)
                processtime = self._log[str(job_id)].get('processingdate', None)
                globalid = self._log[str(job_id)]['globalid']
                redo = self._log[str(job_id)].get('redo', False)

                laststatus = self._globaljoblog[globalid]['laststatus']
                lastjobid = self._globaljoblog[globalid].get('lastjobid', 0)
                startwithinit = self._globaljoblog[globalid].get('startwithinit', False)

                if laststatus is not None and laststatus == 'faulty' and \
                        self._globaljoblog[globalid].get('autojob', False):
                    # breakup job because last job in chain is faulty
                    logger.error("Breakup job {} on device {} - File/Job: {} - previous job in chain was broken "
                                 "(ID: {})", jobtype, origin, file_, job_id)
                    self.write_status_log(str(job_id), field='status', value='terminated')
                    self.send_webhook(job_id=job_id, status=JobReturn.TERMINATED)
                    self._current_job_device.remove(origin)

                    continue

                if (laststatus is None or laststatus == 'future') and not startwithinit and processtime is None and \
                        self._globaljoblog[globalid].get('autojob', False):
                    logger.debug("Autjob (no init run) {} on device {} - File/Job: {} - queued to real starttime "
                                 "(ID: {})", jobtype, origin, file_, job_id)
                    # just schedule job - not process the first time
                    processtime = datetime.timestamp(
                        datetime.now() + timedelta(
                            minutes=self._globaljoblog[globalid].get('algo', 0) + waittime))
                    self.write_status_log(str(job_id), field='processingdate', value=processtime)

                    self._globaljoblog[globalid]['lastjobid'] = job_id
                    self._globaljoblog[globalid]['laststatus'] = 'future'

                    self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                                 counter=counter,
                                 status='future', waittime=waittime, processtime=processtime, redo=redo)

                    self._current_job_device.remove(origin)

                    continue

                if (laststatus is None or laststatus == 'success') and waittime > 0 and processtime is None:
                    # set sleeptime for this job
                    logger.debug('Job {} on device {} - File/Job: {} - queued to real starttime (ID: {})', jobtype,
                                 origin, file_, job_id)

                    self._log[str(job_id)]['processingdate'] = datetime.timestamp(
                        datetime.now() + timedelta(minutes=waittime))

                    self._globaljoblog[globalid]['lastjobid'] = job_id
                    self._globaljoblog[globalid]['laststatus'] = 'success'

                    self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                                 counter=counter,
                                 status='future', waittime=waittime, processtime=processtime, redo=redo)

                    self._current_job_device.remove(origin)

                    continue

                if laststatus is not None and laststatus in ('pending', 'future', 'failure', 'interrupted',
                                                             'not connected') and lastjobid != job_id \
                        and processtime is None:
                    logger.debug('Job {} on device {} - File/Job: {} - queued because last job in jobchain '
                                 'is not processed till now (ID: {})', jobtype, origin, file_, job_id)
                    # skipping because last job in jobchain is not processed till now
                    self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                                 counter=counter,
                                 status='future', waittime=waittime, processtime=processtime, redo=redo)

                    self._current_job_device.remove(origin)

                    continue

                if processtime is not None and datetime.fromtimestamp(processtime) > datetime.now():
                    time.sleep(1)
                    logger.debug('Job {} on device {} - File/Job: {} - queued of processtime in future (ID: {})',
                                 str(jobtype), str(origin), str(file_), str(job_id))
                    self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                                 counter=counter,
                                 status='future', waittime=waittime, processtime=processtime, redo=redo)

                    self._current_job_device.remove(origin)

                    continue

                if job_id in self._log:
                    self._current_job_id.append(job_id)

                    if 'processingdate' in self._log[job_id]:
                        self.write_status_log(str(job_id), field='processingdate', delete=True)

                    logger.info("Job for {} (File/Job: {}) started (ID: {})", origin, file_, job_id)
                    self.write_status_log(str(job_id), field='status', value='processing')
                    self.write_status_log(str(job_id), field='lastprocess', value=int(time.time()))

                    errorcount = 0

                    while jobstatus not in SUCCESS_STATES and errorcount < 3:

                        temp_comm = self._websocket.get_origin_communicator(origin)

                        if temp_comm is None or temp_comm is False:
                            errorcount += 1
                            logger.error("Cannot start job {} on device {} - File/Job: {} - Device not connected "
                                         "(ID: {})", jobtype, origin, file_, job_id)
                            self._globaljoblog[globalid]['laststatus'] = 'not connected'
                            self.write_status_log(str(job_id), field='laststatus', value='not connected')
                            self._globaljoblog[globalid]['lastjobid'] = job_id
                            jobstatus = JobReturn.NOCONNECT
                            time.sleep(5)

                        else:
                            # stop worker
                            self._websocket.set_job_activated(origin)
                            self.write_status_log(str(job_id), field='status', value='starting')
                            try:
                                if self.start_job_type(item, jobtype, temp_comm):
                                    logger.info('Job {} executed successfully - Device {} - File/Job {} (ID: {})',
                                                jobtype, origin, file_, job_id)
                                    if self._log[str(job_id)]['status'] == 'not required':
                                        jobstatus = JobReturn.NOT_REQUIRED
                                    elif self._log[str(job_id)]['status'] == 'not supported':
                                        jobstatus = JobReturn.NOT_SUPPORTED
                                    else:
                                        self.write_status_log(str(job_id), field='status', value='success')
                                        jobstatus = JobReturn.SUCCESS
                                    self._globaljoblog[globalid]['laststatus'] = 'success'
                                    self._globaljoblog[globalid]['lastjobid'] = job_id
                                else:
                                    logger.error("Job {} could not be executed successfully - Device {} - File/Job {} "
                                                 "(ID: {})", jobtype, origin, file_, job_id)
                                    errorcount += 1
                                    self._globaljoblog[globalid]['laststatus'] = 'failure'
                                    self.write_status_log(str(job_id), field='laststatus', value='failure')
                                    self._globaljoblog[globalid]['lastjobid'] = job_id
                                    jobstatus = JobReturn.FAILURE

                                # start worker
                                self._websocket.set_job_deactivated(origin)

                            except Exception:
                                logger.error('Job {} could not be executed successfully (fatal error) - Device {} - '
                                             'File/Job {} (ID: {})', jobtype, origin, file_, job_id)
                                errorcount += 1
                                self._globaljoblog[globalid]['laststatus'] = 'interrupted'
                                self.write_status_log(str(job_id), field='status', value='interrupted')
                                self._globaljoblog[globalid]['lastjobid'] = job_id
                                jobstatus = JobReturn.FAILURE

                    # check jobstatus and readd if possible
                    if jobstatus not in SUCCESS_STATES and \
                            (jobstatus == JobReturn.NOCONNECT and self._args.job_restart_notconnect == 0):
                        logger.error("Job for {} (File/Job: {} - Type {}) failed 3 times in row - aborting (ID: {})",
                                     origin, file_, jobtype, job_id)
                        self._globaljoblog[globalid]['laststatus'] = 'faulty'
                        self.write_status_log(job_id, field='status', value='faulty')

                        if redo and self._globaljoblog[globalid].get('redoonerror', False):
                            logger.info('Re-add this automatic job for {} (File/Job: {} - Type {})  (ID: {})',
                                        origin, file_, jobtype, job_id)
                            self.restart_job(job_id=job_id)
                            self._globaljoblog[globalid]['lastjobid'] = job_id
                            self._globaljoblog[globalid]['laststatus'] = 'success'

                    elif jobstatus in SUCCESS_STATES and redo:
                        logger.info('Re-add this automatic job for {} (File/Job: {} - Type {})  (ID: {})', origin,
                                    file_, jobtype, job_id)
                        self.restart_job(job_id=job_id)

                    elif jobstatus == JobReturn.NOCONNECT and self._args.job_restart_notconnect > 0:
                        logger.error("Job for {} (File/Job: {} - Type {}) failed 3 times in row - requeued it (ID: {})",
                                     origin, file_, jobtype, job_id)
                        processtime = datetime.timestamp(
                            datetime.now() + timedelta(minutes=self._args.job_restart_notconnect))
                        self.write_status_log(str(job_id), field='processingdate', value=processtime)

                        self._globaljoblog[globalid]['lastjobid'] = job_id
                        self._globaljoblog[globalid]['laststatus'] = 'future'

                        self.add_job(globalid=globalid, origin=origin, file=file_, job_id=job_id, type=jobtype,
                                     counter=counter,
                                     status='future', waittime=waittime, processtime=processtime, redo=redo)

                    self.send_webhook(job_id=job_id, status=jobstatus)

                    self._current_job_id.remove(job_id)
                    self._current_job_device.remove(origin)
                    errorcount = 0
                    time.sleep(10)

            except KeyboardInterrupt:
                logger.info("process_update_queue-{} received keyboard interrupt, stopping", threadnumber)
                break

            time.sleep(2)
        logger.info("Updater thread stopped")

    @logger.catch()
    def preadd_job(self, origin, job, job_id, job_type, globalid=None):
        logger.info('Adding Job {} for Device {} - File/Job: {} (ID: {})', job_type, origin, job, job_id)

        globalid = globalid if globalid is not None else job_id

        if globalid not in self._globaljoblog:
            self._globaljoblog[globalid] = {}

        self._globaljoblog[globalid]['laststatus'] = None
        self._globaljoblog[globalid]['lastjobend'] = None

        if JobType[job_type.split('.')[1]] == JobType.CHAIN:

            for subjob in self._commands[job]:
                logger.debug2(subjob)
                self.add_job(globalid=globalid, origin=origin, file=subjob['SYNTAX'], job_id=int(time.time()),
                             job_type=subjob['TYPE'], waittime=subjob.get('WAITTIME', 0),
                             redo=self._globaljoblog[globalid].get('redo', False),
                             fieldname=subjob.get('FIELDNAME', 'unknown'), jobname=job)
                time.sleep(1)
        else:
            self.add_job(globalid=globalid, origin=origin, file=job, job_id=int(job_id), job_type=job_type)

    @logger.catch()
    def add_job(self, globalid, origin, job, job_id: int, job_type, counter=0, status='pending', waittime=0,
                processtime=None, redo=False, fieldname=None, jobname=None):
        if str(job_id) not in self._log:
            log_entry = ({
                'id': int(job_id),
                'origin': origin,
                'jobname': jobname if jobname is not None else job,
                'file': job,
                'status': status,
                'fieldname': fieldname if fieldname is not None else "unknown",
                'counter': int(counter),
                'jobtype': str(job_type),
                'globalid': int(globalid),
                'waittime': waittime,
                'laststatus': 'init',
                'redo': redo,
                'auto': self._globaljoblog[globalid].get('autojob', False)
            })
            self.write_status_log(str(job_id), field=log_entry)
        else:
            self.write_status_log(str(job_id), field='status', value=status)
            self.write_status_log(str(job_id), field='counter', value=counter)

        self._update_queue.put(str(job_id))

    def write_status_log(self, job_id, field=None, value=None, delete=False):
        self._update_mutex.acquire()
        try:
            if delete:
                if field is None:
                    del self._log[str(job_id)]
                else:
                    if field in self._log[str(job_id)]:
                        del self._log[str(job_id)][field]
            else:
                if str(job_id) not in self._log:
                    self._log[str(job_id)] = {}
                if value is not None:
                    self._log[str(job_id)][field] = value
                else:
                    self._log[str(job_id)] = field
        finally:
            self._update_mutex.release()

        self.update_status_log()

    def update_status_log(self):
        with open('update_log.json', 'w') as outfile:
            json.dump(self._log, outfile, indent=4)

    @logger.catch()
    def delete_log_id(self, job_id: str):
        if job_id not in self._current_job_id:
            self.write_status_log(str(job_id), delete=True)
            return True
        return False

    def get_log(self, withautojobs=False):
        if withautojobs:
            return [self._log[x] for x in self._log if self._log[x].get('auto', False)]
        return [self._log[x] for x in self._log if not self._log[x].get('auto', False)]

    @logger.catch()
    def start_job_type(self, item, jobtype, ws_conn):
        try:
            jobtype = JobType[jobtype.split('.')[1]]
            if jobtype == JobType.INSTALLATION:
                file_ = self._log[str(item)]['file']
                if str(file_).lower().endswith(".apk"):
                    returning = ws_conn.install_apk(300, filepath=os.path.join(self._args.upload_path, file_))
                elif str(file_).lower().endswith(".zip"):
                    returning = ws_conn.install_bundle(600, filepath=os.path.join(self._args.upload_path, file_))
                else:
                    # unknown filetype
                    returning = False
                return returning if not 'RemoteGpsController'.lower() in str(file_).lower() else True
            elif jobtype == jobtype.SMART_UPDATE:
                package_ver: str = None
                package_raw = self._log[str(item)]['file']
                version_job = "dumpsys package %s | grep versionName" % (package_raw,)
                architecture_job = ws_conn.passthrough('getprop ro.product.cpu.abi')
                package_ver_job = ws_conn.passthrough(version_job)
                try:
                    architecture_raw = re.search(r'\[(\S+)\]', architecture_job).group(1)
                except AttributeError:
                    logger.warning('Unable to determine the architecture of the device')
                    return False
                try:
                    package_ver = re.search(r'versionName=([0-9\.]+)', package_ver_job).group(1)
                except AttributeError:
                    if package_ver_job and package_ver_job.split('\n')[0].strip() == 'OK':
                        logger.info('No information returned.  Assuming package is not installed')
                    else:
                        logger.warning('Unable to determine version for {}: {}', self._log[str(item)]['file'],
                                       package_ver_job)
                        return False
                package = getattr(APKType, APKPackage(package_raw).name)
                architecture = lookup_arch_enum(architecture_raw)
                package_all: MADPackages = self._storage_obj.get_current_package_info(package)
                if package_all is None:
                    logger.warning('No MAD APK for {} [{}]', package, architecture.name)
                    return False
                try:
                    mad_apk = package_all[architecture]
                except KeyError:
                    architecture = APKArch.noarch
                    mad_apk = package_all[architecture.noarch]

                if mad_apk.filename is None:
                    logger.warning('No MAD APK for {} [{}]', package, architecture.name)
                    return False
                # Validate it is supported
                if package == APKType.pogo:
                    if not supported_pogo_version(architecture, mad_apk.version):
                        self.write_status_log(str(item), field='status', value='not supported')
                        return True
                if not is_newer_version(mad_apk.version, package_ver):
                    logger.info('Both versions are the same.  No update required')
                    self.write_status_log(str(item), field='status', value='not required')
                    return True
                else:
                    logger.info('Smart Update APK Installation for {} to {}', package.name,
                                self._log[str(item)]['origin'])
                    apk_file = bytes()
                    for chunk in file_generator(self._db, self._storage_obj, package, architecture):
                        apk_file += chunk
                    if mad_apk.mimetype == 'application/zip':
                        returning = ws_conn.install_bundle(300, data=apk_file)
                    else:
                        returning = ws_conn.install_apk(300, data=apk_file)
                    return returning if not 'RemoteGpsController'.lower() in str(
                        self._log[str(item)]['file']).lower() else True
            elif jobtype == JobType.REBOOT:
                return ws_conn.reboot()
            elif jobtype == JobType.RESTART:
                return ws_conn.restart_app("com.nianticlabs.pokemongo")
            elif jobtype == JobType.STOP:
                return ws_conn.stop_app("com.nianticlabs.pokemongo")
            elif jobtype == JobType.START:
                return ws_conn.start_app("com.nianticlabs.pokemongo")
            elif jobtype == JobType.PASSTHROUGH:
                command = self._log[str(item)]['file']
                returning = ws_conn.passthrough(command).replace('\r', '').replace('\n', '').replace('  ', '')
                self.write_status_log(str(item), field='returning', value=returning)
                self.set_returning(origin=self._log[str(item)]['origin'],
                                   fieldname=self._log[str(item)].get('fieldname'),
                                   value=returning)
                return returning if 'KO' not in returning else False
            return False
        except Exception as e:
            logger.error('Error while getting response from device - Reason: {}', e)
        return False

    def delete_log(self, onlysuccess=False):
        if onlysuccess:
            for job in self._log.copy():
                if self._log[job]['status'] in ['success', 'not required'] and not self._log[job].get('redo',
                                                                                                      False):
                    self.write_status_log(str(job), delete=True)

        else:
            for job in self._log.copy():
                if not self._log[job].get('redo', False):
                    self.delete_log_id(job)

    def send_webhook(self, job_id, status):
        if not self._log[str(job_id)]['auto']:
            return

        try:
            if JobReturn(status).name not in self._args.job_dt_send_type.split(
                    '|') or not self._args.job_dt_wh:
                return

            from discord_webhook import DiscordWebhook, DiscordEmbed
            _webhook = DiscordWebhook(url=self._args.job_dt_wh_url)

            origin = self._log[str(job_id)]['origin']
            file_ = self._log[str(job_id)]['file']
            processtime = self._log[str(job_id)].get('processingdate', None)
            returning = self._log[str(job_id)].get('returning', '-')

            logger.info("Send discord status for device {} (Job: {})", origin, file_)

            embed = DiscordEmbed(title='MAD Job Status', description='Automatic Job processed', color=242424)
            embed.set_author(name='MADBOT')
            embed.add_embed_field(name='Origin', value=origin)
            embed.add_embed_field(name='Jobname', value=file_)
            embed.add_embed_field(name='Retuning', value=returning)
            embed.add_embed_field(name='Status', value=JobReturn(status).name)
            embed.add_embed_field(name='Next run',
                                  value=str(datetime.fromtimestamp(
                                      processtime) if processtime is not None else "-"))
            _webhook.add_embed(embed)
            _webhook.execute()
            embed = None
        except Exception as e:
            logger.error('Cannot send discord webhook for origin {} - Job {} - Reason: {}', origin, file_, e)

    def load_automatic_jobs(self):
        self._globaljoblog = {}
        autocommandfile = os.path.join(self._args.file_path, 'autocommands.json')
        if os.path.exists(autocommandfile):
            with open(autocommandfile) as cmdfile:
                autocommands = json.loads(cmdfile.read())

            logger.info('Found {} autojobs - add them', len(autocommands))

            for autocommand in autocommands:
                origins = autocommand['origins'].split('|')
                for origin in origins:
                    redo = autocommand.get('redo', False)
                    algo = self.get_job_algo_value(algotyp=autocommand.get('algotype', 'flex'),
                                                   algovalue=autocommand.get('algovalue', 0))
                    startwithinit = autocommand.get('startwithinit', False)

                    job = autocommand['job']

                    globalid = int(time.time())

                    self._globaljoblog[globalid] = {}
                    self._globaljoblog[globalid]['redo'] = redo
                    self._globaljoblog[globalid]['algo'] = algo
                    self._globaljoblog[globalid]['algovalue'] = autocommand.get('algovalue', 0)
                    self._globaljoblog[globalid]['algotype'] = autocommand.get('algotype', 'flex')
                    self._globaljoblog[globalid]['startwithinit'] = startwithinit
                    self._globaljoblog[globalid]['autojob'] = True
                    self._globaljoblog[globalid]['redoonerror'] = autocommand.get('redoonerror', False)

                    self.preadd_job(origin=origin, job=job, job_id=int(time.time()),
                                    type=str(JobType.CHAIN))
                    # get a unique id !
                    time.sleep(1)
        else:
            logger.info('Did not find any automatic jobs')

    def get_job_algo_value(self, algotyp, algovalue):
        if algotyp == "loop":
            # returning value as minutes
            return algovalue

        # calc diff in minutes to get exact starttime

        algotime = algovalue.split(':')
        tm = datetime.now().replace(
            hour=int(algotime[0]), minute=int(algotime[1]), second=0, microsecond=0)

        return (tm - datetime.now()).seconds / 60

    def set_returning(self, origin, fieldname, value):
        if origin not in self._returning:
            self._returning[origin] = {}

        if fieldname not in self._returning[origin]:
            self._returning[origin][fieldname] = ""

        self._returning[origin][fieldname] = str(value)
