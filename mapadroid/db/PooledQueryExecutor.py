from multiprocessing import Lock, Semaphore
from multiprocessing.managers import SyncManager
import mysql
from mysql.connector import ProgrammingError
from mysql.connector.pooling import MySQLConnectionPool
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.database)


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

    def setup_cursor(self, conn, **kwargs):
        conn_args = {}
        use_dict = kwargs.get('use_dict', False)
        prepared = kwargs.get('prepared', False)
        if use_dict:
            conn_args['dictionary'] = True
        if prepared:
            conn_args['prepared'] = True
        return conn.cursor(**conn_args)

    def execute(self, sql, args=(), commit=False, **kwargs):
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
        cursor = self.setup_cursor(conn, **kwargs)
        get_id = kwargs.get('get_id', False)
        get_dict = kwargs.get('get_dict', False)
        raise_exc = kwargs.get('raise_exc', False)
        suppress_log = kwargs.get('suppress_log', False)
        try:
            multi = False
            if type(args) != tuple and args is not None:
                args = (args,)
            if sql.count(';') > 1:
                multi = True
                for res in conn.cmd_query_iter(sql):
                    pass
            else:
                cursor.execute(sql, args)
            logger.debug3(cursor.statement)
            if commit is True:
                conn.commit()
                if not multi:
                    affected_rows = cursor.rowcount
                    if get_id:
                        return cursor.lastrowid
                    else:
                        return affected_rows
            else:
                if not multi:
                    res = cursor.fetchall()
                    if get_dict:
                        return self.__convert_to_dict(cursor.column_names, res)
                    return res
        except mysql.connector.Error as err:
            if not suppress_log:
                logger.error("Failed executing query: {}, error: {}", str(sql), str(err))
            logger.debug3(sql)
            logger.debug3(args)
            if raise_exc:
                raise err
            return None
        except Exception as e:
            logger.error("Unspecified exception in dbWrapper: {}", str(e))
            return None
        finally:
            self.close(conn, cursor)
            self._connection_semaphore.release()

    def executemany(self, sql, args, commit=False, **kwargs):
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
            cursor.executemany(sql, args, **kwargs)

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

    # ===================================================
    # =============== DB Helper Functions ===============
    # ===================================================

    def __convert_to_dict(self, descr, rows):
        desc = [n for n in descr]
        return [dict(zip(desc, row)) for row in rows]

    def __create_clause(self, col_names, col_subs):
        """ Creates a clause and handles lists
        Args:
            col_names (list): List of column names
            col_subs (list): List of column value substitutions
        Returns (list):
            List of elements for the clause
        """
        clause = []
        for ind, name in enumerate(col_names):
            if col_subs[ind].find(",") != -1:
                clause.append("`%s` IN (%s)" % (name, col_subs[ind]))
            else:
                clause.append("`%s` = %s" % (name, col_subs[ind]))
        return clause

    def __fix_table(self, table):
        """ Encapsualtes the table in backticks
        Args:
            table (str): Table to encapsulate
        Returns (str):
            Encapsulated table
        """
        split_table = table.split(".")
        table_name = ""
        if len(split_table) > 2:
            raise Exception("Invalid table format, %s" % table)
        for name in split_table:
            name = name.replace("`", "")
            if len(table_name) != 0:
                table_name += "."
            table_name += "`%s`" % name
        return table_name

    def __process_literals(self, optype, keyvals, literals):
        """ Processes literals and returns a tuple containing all data required for the query
        Args:
            keyvals (dict): Data to insert into the table
            literals (list): Datapoints that should not be escaped
            optype (str): Type of operation
        Returns (tuple):
            (Column names, Column Substitutions, Column Values, Literal Values, OnDuplicate)
        """
        column_names = []
        column_substituion = []
        column_values = []
        literal_values = []
        ondupe_out = []
        for key, value in keyvals.items():
            if type(value) is list and optype not in ["DELETE", "UPDATE"]:
                raise Exception("Unable to process a list in key %s" % key)
            column_names += [key]
            # Determine the type of data to insert
            sub_op = "%%s"
            if key in literals:
                sub_op = "%s"
            # Number of times to repeat
            num_times = 1
            if type(value) is list:
                num_times = len(value)
            column_substituion += [",".join(sub_op for _ in range(0, num_times))]
            # Add to the entries
            if key in literals:
                if type(value) is list:
                    literal_values += value
                else:
                    literal_values += [value]
            else:
                if type(value) is list:
                    column_values += value
                else:
                    column_values += [value]
        for key, value in keyvals.items():
            if optype == "ON DUPLICATE":
                tmp_value = "`%s` = %%s" % key
                if key in literals:
                    tmp_value = tmp_value % value
                else:
                    column_values += [value]
                ondupe_out += [tmp_value]
        return (column_names, column_substituion, column_values, literal_values, ondupe_out)

    def autofetch_all(self, sql, args=(), **kwargs):
        """ Fetch all data and have it returned as a dictionary """
        return self.execute(sql, args=args, get_dict=True, raise_exc=True, **kwargs)

    def autofetch_value(self, sql, args=(), **kwargs):
        """ Fetch the first value from the first row """
        data = self.execute(sql, args=args, raise_exc=True, **kwargs)
        if not data or len(data) == 0:
            return None
        return data[0][0]

    def autofetch_row(self, sql, args=(), **kwargs):
        """ Fetch the first row and have it return as a dictionary """
        # TODO - Force LIMIT 1
        data = self.execute(sql, args=args, get_dict=True, raise_exc=True, **kwargs)
        if not data or len(data) == 0:
            return {}
        return data[0]

    def autofetch_column(self, sql, args=None, **kwargs):
        """ get one field for 0, 1, or more rows in a query and return the result in a list
        """
        data = self.execute(sql, args=args, raise_exc=True, **kwargs)
        if data is None:
            data = []
        returned_vals = []
        for row in data:
            returned_vals.append(row[0])
        return returned_vals

    def autoexec_delete(self, table, keyvals, literals=[], where_append=[], **kwargs):
        """ Performs a delete
        Args:
            table (str): Table to run the query against
            keyvals (dict): Data to insert into the table
            literals (list): Datapoints that should not be escaped
            where_append (list): Additional data to append to the query
        """
        if type(keyvals) is not dict:
            raise Exception("Data must be a dictionary")
        if type(literals) is not list:
            raise Exception("Literals must be a list")
        table = self.__fix_table(table)
        parsed_literals = self.__process_literals("DELETE", keyvals, literals)
        (column_names, column_substituion, column_values, literal_values, _) = parsed_literals
        query = "DELETE FROM %s\nWHERE "
        where_clauses = where_append + self.__create_clause(column_names, column_substituion)
        query += "\nAND ".join(k for k in where_clauses)
        literal_values = [table] + literal_values
        query = query % tuple(literal_values)
        self.execute(query, args=tuple(column_values), commit=True, raise_exc=True, **kwargs)

    def autoexec_insert(self, table, keyvals, literals=[], optype="INSERT", **kwargs):
        """ Auto-inserts into a table and handles all escaping
        Args:
            table (str): Table to run the query against
            keyvals (dict): Data to insert into the table
            literals (list): Datapoints that should not be escaped
            optype (str): Type of operation.  Valid operations are ["INSERT", "REPLACE", "INSERT IGNORE",
                "ON DUPLICATE"]
            log (bool): If the query should be logged
            logger (logging.logger): Logger that will be used if log = True
        Returns (int):
            Primary key for the row
        """
        optype = optype.upper()
        if optype not in ["INSERT", "REPLACE", "INSERT IGNORE", "ON DUPLICATE"]:
            raise ProgrammingError("MySQL operation must be 'INSERT', 'REPLACE', 'INSERT IGNORE', 'ON DUPLICATE',"
                                   "got '%s'" % optype)
        if type(keyvals) is not dict:
            raise Exception("Data must be a dictionary")
        if type(literals) is not list:
            raise Exception("Literals must be a list")
        table = self.__fix_table(table)
        parsed_literals = self.__process_literals(optype, keyvals, literals)
        (column_names, column_substituion, column_values, literal_values, ondupe_out) = parsed_literals
        ondupe_values = []
        inital_type = optype
        if optype == "ON DUPLICATE":
            inital_type = "INSERT"
        if inital_type in ["INSERT", "REPLACE"]:
            inital_type += " INTO"
        rownames = ",".join("`%s`" % k for k in column_names)
        rowvalues = ", ".join(k for k in column_substituion)
        query = "%s %s\n" \
                "(%s)\n" \
                "VALUES(%s)" % (inital_type, table, rownames, rowvalues) % tuple(literal_values)
        if optype == "ON DUPLICATE":
            dupe_out = ",\n".join("%s" % k for k in ondupe_out)
            query += "\nON DUPLICATE KEY UPDATE\n" \
                     "%s" % dupe_out
            column_values += ondupe_values
        return self.execute(query, args=tuple(column_values), commit=True, get_id=True, raise_exc=True, **kwargs)

    def autoexec_update(self, table, set_keyvals, literals=[], where_keyvals={}, where_literals=[], **kwargs):
        """ Auto-updates into a table and handles all escaping
        Args:
            table (str): Table to run the query against
            set_keyvals (dict): Data to set
            set_literals (list): Datapoints that should not be escaped
            where_keyvals (dict): Data used in the where clause
            where_literals (list): Datapoints that should not be escaped
        """
        if type(set_keyvals) is not dict:
            raise Exception("Set Keyvals must be a dictionary")
        if type(literals) is not list:
            raise Exception("Literals must be a list")
        if type(where_keyvals) is not dict:
            raise Exception("Where Keyvals must be a dictionary")
        if type(where_literals) is not list:
            raise Exception("Literals must be a list")
        parsed_set = self.__process_literals("SET", set_keyvals, literals)
        (set_col_names, set_col_sub, set_val, set_literal_val, _) = parsed_set
        parsed_where = self.__process_literals("UPDATE", where_keyvals, where_literals)
        (where_col_names, where_col_sub, where_val, where_literal_val, _) = parsed_where
        first_sub = [table]
        actual_values = set_val + where_val
        set_clause = self.__create_clause(set_col_names, set_col_sub)
        first_sub.append(",".join(set_clause) % tuple(set_literal_val))
        query = "UPDATE %s\n" \
                "SET %s"
        if where_col_names:
            query += "\nWHERE %s"
            where_clause = self.__create_clause(where_col_names, where_col_sub)
            first_sub.append("\nAND".join(where_clause) % tuple(where_literal_val))
        query = query % tuple(first_sub)
        self.execute(query, args=tuple(actual_values), commit=True, raise_exc=True, **kwargs)
