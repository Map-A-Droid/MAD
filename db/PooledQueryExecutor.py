from multiprocessing import Lock, Semaphore
from multiprocessing.managers import SyncManager
import mysql
from mysql.connector.pooling import MySQLConnectionPool
from utils.logging import logger

class PooledQuerySyncManager(SyncManager):
    pass

class PooledQueryExecutor:

    def __init__(self, host, port, username, password, database, poolsize=1):
        self.host = host
        self.port = port
        self.user = username
        self.password = password
        self.database = database
        self._poolsize = poolsize

        self._pool = None
        self._pool_mutex = Lock()

        self._connection_semaphore = Semaphore(poolsize)

        self._init_pool()


    def _init_pool(self):
        logger.info("Connecting to DB")
        dbconfig = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database
        }
        self._pool_mutex.acquire()
        self._pool = MySQLConnectionPool(pool_name="db_wrapper_pool",
                                        pool_size=self._poolsize,
                                        **dbconfig)
        self._pool_mutex.release()


    def close(self, conn, cursor):
        """
        A method used to close connection of mysql.
        :param conn:
        :param cursor:
        :return:
        """
        cursor.close()
        conn.close()


    def execute(self, sql, args=None, commit=False):
        """
        Execute a sql, it could be with args and with out args. The usage is
        similar with execute() function in module pymysql.
        :param sql: sql clause
        :param args: args need by sql clause
        :param commit: whether to commit
        :return: if commit, return None, else, return result
        """
        self._connection_semaphore.acquire()
        conn = self._pool.get_connection()
        cursor = conn.cursor()

        # TODO: consider catching OperationalError
        # try:
        #     cursor = conn.cursor()
        # except OperationalError as e:
        #     logger.error("OperationalError trying to acquire a DB cursor: {}", str(e))
        #     conn.rollback()
        #     return None
        try:
            if args:
                cursor.execute(sql, args)
            else:
                cursor.execute(sql)
            if commit is True:
                affected_rows = cursor.rowcount
                conn.commit()
                return affected_rows
            else:
                res = cursor.fetchall()
                return res
        except mysql.connector.Error as err:
            logger.error("Failed executing query: {}, error: {}", str(sql), str(err))
            return None
        except Exception as e:
            logger.error("Unspecified exception in dbWrapper: {}", str(e))
            return None
        finally:
            self.close(conn, cursor)
            self._connection_semaphore.release()


    def executemany(self, sql, args, commit=False):
        """
        Execute with many args. Similar with executemany() function in pymysql.
        args should be a sequence.
        :param sql: sql clause
        :param args: args
        :param commit: commit or not.
        :return: if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        self._connection_semaphore.acquire()
        conn = self._pool.get_connection()
        cursor = conn.cursor()

        try:
            cursor.executemany(sql, args)

            if commit is True:
                conn.commit()
                return None
            else:
                res = cursor.fetchall()
                return res
        except mysql.connector.Error as err:
            logger.error("Failed executing query: {}", str(err))
            return None
        except Exception as e:
            logger.error("Unspecified exception in dbWrapper: {}", str(e))
            return None
        finally:
            self.close(conn, cursor)
            self._connection_semaphore.release()
