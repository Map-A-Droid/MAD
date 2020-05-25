import mapadroid.utils.pluginBase

class Identity(mapadroid.utils.pluginBase.Plugin):
    """This plugin is just the identity function: it returns the argument
    """
    def __init__(self):
        super().__init__()
        self.description = 'ExamBaseple Plugin'

    def perform_operation(self, db_wrapper, args, madmin, logger, data_manager,
                          mapping_manager, jobstatus, device_Updater, ws_server):
        """The actual implementation of the identity plugin is to just return the
        argument
        """
        return True
