"""Define Database Tables and Transaction Class"""
from __future__ import annotations
import os
import ast
import shlex
import pathlib
import datetime
from enum import Enum
from collections import defaultdict
from typing import Sequence, List, Type, TypeVar, Any, Tuple, Union, Iterable, Mapping
from contextlib import nullcontext

import MySQLdb

from hydra_farm.utils import yaml_cache
from hydra_farm.utils import hydra_utils
from hydra_farm.database import db_login
from hydra_farm.database.enums import HydraStatus
from hydra_farm.utils.logging_setup import logger
from hydra_farm.networking.connections import HydraRequest, HydraResponse, send_request

_config = yaml_cache.get_hydra_cfg()
_UNIT_TEST = bool(ast.literal_eval(os.environ.get('Hydra_Unit_Test', "False")))
_T = TypeVar('_T', bound='AbstractHydraTable')  # For type hinting on tables
STUCK_STATUS = {HydraStatus.STARTED, HydraStatus.PENDING}


class Transaction(object):
    """SQL Transaction Context Manger. Stores login info as class variables.

    """
    host, db_username, db_password, database_name, port = db_login.get_database_info()
    in_transaction = False

    def __init__(self):
        self.db = MySQLdb.Connect(host=self.host, user=self.db_username, passwd=self.db_password,
                                  db=self.database_name, port=self.port)
        self.cur = self.db.cursor()
        self.cur.execute("SET autocommit = 1")

    def __enter__(self):
        self.cur.execute("START TRANSACTION")
        self.in_transaction = True
        return self

    def __exit__(self, error_type, traceback, value):
        if error_type is None:
            self.cur.execute("COMMIT")
        else:
            logger.exception("ROLLBACK %s", self)
            self.cur.execute("ROLLBACK")
        self.db.close()
        self.in_transaction = False


class AbstractHydraTable(object):
    """Abstract Database Definition with fetch, insert, refresh, update, and update_attr operations. Also
    overrides __get_attr__ to attempt to lookup missing attrs on the db.

    Class Attributes:
        table_name (str): Name of the table.
        primary_key (str): Name of the primary key on the table.
        columns (set): Set of columns on the table, verified by unit testing.
        _auto_column (str): Auto increment column name for the table, default None.
        _from_db (bool): Set True when the record is queried from the db, default False when the class is instantiated
        to be inserted into the db.

    """
    table_name: str
    primary_key: str
    columns: set
    _auto_column: str = None
    _from_db: bool = False

    def __init__(self, data_dict: dict = None):
        """Initialize the table

        Args:
            data_dict (dict[col: value]): Dict where column: value.

        """
        if data_dict is None:
            data_dict = {}
        self._dirty = set()
        self.do_refresh(data_dict)

    def __repr__(self):
        return f"<{type(self).__name__}> [{self.primary_key}: {getattr(self, self.primary_key)}]"

    def __setattr__(self, key: str, value: Any):
        """Override __setattr__ to add cols to _dirty for the _update method.

        """
        if isinstance(value, Enum):
            value = value.value
        if key in self.columns:
            self._dirty.add(key)
        return super().__setattr__(key, value)

    def __getattr__(self, attr: str) -> Any:
        """Define __getattr__ to search the db for cols not already set on the class before failing. Useful
        for situations where you only only a few cols and end up needing data from another one.

        """
        if not self._from_db or attr not in self.columns:
            # Raise an Attribute Error
            super().__getattribute__(attr)
        value = self._getattr_col(attr)
        self.set_no_dirty(attr, value)
        return value

    def get_set_columns(self) -> list:
        """Return a list of columns which has been set on this instance, ie the columns which were fetched.

        Returns:
            list: List of columns which has been set on this instance.

        """
        return [c for c in self.columns if hydra_utils.hasattr_static(self, c)]

    def get_attr_static(self, attr: str) -> Any:
        """getattr without dynamic lookup via __getattr__ or __getattribute__

        Args:
            attr (str): Attr to get from this instance if it is set.

        Returns:
            Any: The value if the attr is set, None if not.

        """
        if not hydra_utils.hasattr_static(self, attr):
            return None
        return getattr(self, attr)

    def refresh(self, explicit_transaction: Transaction = None, all_columns: bool = False):
        """Refresh this instance with the latest data from the DB.

        Args:
            explicit_transaction (Transaction): Either an explicit db transaction or None.
            all_columns (bool): If True will fetch all columns, default False will fetch  columns set on this instance.

        """
        if all_columns:
            columns = '*'
        else:
            columns = set(self.get_set_columns())
            columns.add(self.primary_key)
            columns = ','.join(columns)

        select = f"SELECT {columns} FROM {self.table_name} WHERE {self.primary_key} = %s"

        t, transaction_context = self._get_transaction(explicit_transaction)
        with transaction_context:
            result = self._do_fetch(t, select, (getattr(self, self.primary_key),))

        self.do_refresh(result[0])

    @staticmethod
    def bulk_refresh(records: List[_T]):
        """Refresh a list of instances with the latest from the DB, grouping by table for speed. Currently just selects
        * instead of individual cols since I think the overhead of comparing cols is higher than selecting *.

        Args:
            records List[T]: List of AbstractHydraTable tables.

        """
        # Group records by class type
        record_by_type = defaultdict(dict)
        for r in records:
            record_by_type[type(r)][getattr(r, r.primary_key)] = r

        # Refresh each class type in single transaction
        # I think the overhead of comparing cols is higher than selecting * so we're just doing that for now
        for cls, cls_records in record_by_type.items():
            primary_key = cls.primary_key
            keys_str = ','.join(['%s' for _ in cls_records])
            select = f"SELECT * FROM {cls.table_name} WHERE {primary_key} in ({keys_str})"
            with Transaction() as t:
                result = cls._do_fetch(t, select, tuple(cls_records.keys()))

            for r in result:
                key = r[primary_key]
                cls_records[key].do_refresh(r)

    def do_refresh(self, data: dict):
        """Takes in a dict where {col: value} and updates itself with the values from the dict.

        Args:
            data (dict): Dict where {col: value}

        Returns:

        """
        for k, v in data.items():
            if k in self.columns:
                setattr(self, k, v)
            else:
                logger.error('%s is not in %s.columns', k, type(self).__name__)

    @property
    def status_enum(self) -> HydraStatus:
        """Returns the status as an enum instead of a string. 
        
        Returns:
            AbstractStatus: Enum of the status.

        """
        return HydraStatus(self.status)

    @classmethod
    def _do_fetch(cls, t: Transaction, sel: str, args: Union[Iterable, Mapping]) -> Tuple[dict]:
        """Do the actual fetch from the db.

        Args:
            t (Transaction): Transaction object that has been `__enter__`ed
            sel (str): SQL select clause.
            args (tuple): Args for select clause.

        Returns:
            Tuple[dict]: List of class instances for each row selected in the table.

        """
        if not t.in_transaction:
            logger.error('Must enter transaction before fetching.')
            return tuple()
        sel = hydra_utils.strip_sql_query(sel)
        logger.debug(sel, *args)
        t.cur.execute(sel, args)
        names = [d[0] for d in t.cur.description]
        result = tuple({k: v for k, v in zip(names, tup)} for tup in t.cur.fetchall())
        return result

    @classmethod
    def fetch(cls: Type[_T], clause: str = None, args: Union[Iterable, Mapping] = None, columns: Sequence = None,
              explicit_transaction: Transaction = None) -> List[_T]:
        """Fetch row(s) from the database and return as DB instance(s).

        Args:
            clause (str): Where clause such as `WHERE id = %s`. Default all rows.
            args (tuple): Args for the clause in the form of a tuple. Default tuple().
            columns (Sequence): Sequence of columns to select, default *.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            list: List of class instances for each row selected.

        """
        clause = clause if clause else str()
        args = args if args else tuple()
        col_sel = '*'
        if columns:
            columns = set(map(str, columns))
            columns.add(cls.primary_key)
            col_sel = ','.join(columns)

        query = f"SELECT {col_sel} FROM {cls.table_name} {clause}"

        t, transaction_context = cls._get_transaction(explicit_transaction)
        with transaction_context:
            result = cls._do_fetch(t, query, args)

        result = [cls(r) for r in result]
        for r in result:
            r._from_db = True

        return result

    def _getattr_col(self, col: str) -> Any:
        """Gets a value from a given col on the database.

        Args:
            col (str): Col name

        Returns:
            Any: Value of the col for this row on the db.

        """
        query = f"SELECT {col} FROM {self.table_name} WHERE {self.primary_key} = %s"
        args = (getattr(self, self.primary_key),)
        logger.debug(query, *args)

        with Transaction() as t:
            t.cur.execute(query, args)
            [result] = t.cur.fetchone()

        logger.debug('Result: %s', result)
        return result

    def set_no_dirty(self, attr: str, value: Any) -> Any:
        """Sets an attr and then removes it from _dirty to avoid an update during update().

        Args:
            attr (str): Attr to set on the class
            value (Any): Value to set on the attr

        Returns:
            Any: The input value

        """
        setattr(self, attr, value)
        try:
            self._dirty.remove(attr)
        except KeyError:
            pass
        return value

    @staticmethod
    def _get_transaction(explicit_transaction: Transaction) -> Tuple[Transaction, Union[nullcontext, Transaction]]:
        """Returns a Transaction (t) and a transaction context (transaction_context) for context
        management. If no explicit transaction is passed, these are both the same thing. If one is
        passed, then the transaction context is a null context so that the context manager doesn't
        actually do anything.

        Args:
            explicit_transaction (Transaction): Either an explicit db transaction or None

        Returns:
            (Transaction, Transaction): A tuple of (transaction, transaction_context).

        """
        if isinstance(explicit_transaction, Transaction):
            t = explicit_transaction
            transaction_context = nullcontext()
        else:
            t = Transaction()
            transaction_context = t
        return t, transaction_context

    def insert(self, explicit_transaction: Transaction = None) -> _T:
        """Insert this item into the table.

        Args:
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            self

        """
        data = {}
        for n in list(self.columns):
            try:
                data[n] = getattr(self, n)
            except AttributeError:
                continue

        names = tuple(data.keys())
        values = tuple(data.values())

        _names = ", ".join(names)
        _fields = ", ".join(['%s' for _ in names])
        query = f"INSERT INTO {self.table_name} ({_names}) VALUES ({_fields})"
        logger.debug(query, *values)

        t, transaction_context = self._get_transaction(explicit_transaction)
        with transaction_context:
            t.cur.execute(query, values)
            if self._auto_column:
                t.cur.execute("SELECT last_insert_id()")
                [insert_id] = t.cur.fetchone()
                setattr(self, self._auto_column, insert_id)

        return self

    def update(self, explicit_transaction: Transaction = None) -> bool:
        """Update the attrs set on the instance to the database using _dirty.

        Examples:
            In this example we fetch a render ndoe, set the host name, and then update the table.
            >>> node = HydraRenderNode.fetch('WHERE ID = %s', (1,))[0]
            >>> node.host = 'test_host'
            >>> node.update()
            >>> node._getattr_col('test_host')
            >>> 'test_host'

        Args:
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            bool: True if successful, False if not or nothing was in _dirty to udpate.

        """
        if not self._dirty:
            logger.info('Nothing to update %s', self)
            return False

        names = self._dirty
        assign = ", ".join([f"{n} = %s" for n in names])
        values = tuple(getattr(self, n) for n in names)
        query = f"UPDATE {self.table_name} SET {assign} WHERE {self.primary_key} = {getattr(self, self.primary_key)}"
        logger.debug(query, *values)

        t, transaction_context = self._get_transaction(explicit_transaction)
        with transaction_context:
            t.cur.execute(query, values)
            self._dirty.clear()
        return True

    def update_attr(self, attr: str, value: Any, explicit_transaction: Transaction = None) -> bool:
        """Update a single col on the db and on this instance.

        In this example we fetch a render node and change the host name.
            >>> node = HydraRenderNode.fetch('WHERE ID = %s', (1,))[0]
            >>> node.update_attr('host', 'test_host')
            >>> node._getattr_col('test_host')
            >>> 'test_host'

        Args:
            attr (str): Col to update
            value (Any): Value to set
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            bool: True if successful, False if not.

        """
        if attr not in self.columns:
            logger.error('%s not found in %s', attr, self)
            return False

        if isinstance(value, Enum):
            value = value.value

        query = f"UPDATE {self.table_name} SET {attr} = %s WHERE {self.primary_key} = %s"
        args = (value, getattr(self, self.primary_key))
        logger.debug(query, *args)

        t, transaction_context = self._get_transaction(explicit_transaction)
        with transaction_context:
            t.cur.execute(query, args)

        self.set_no_dirty(attr, value)

        return True

    def as_dict(self, all_columns: bool = False) -> dict:
        """Dump this record as a dict.

        Args:
            all_columns (bool): If True will pull all columns before dumping. Default False will only dump columns
            set on this instance.

        Returns:
            dict: This instance in the form of a dict.

        """
        # If all_columns is True and not all columns are set, fetch everything
        if all_columns and not len(self.get_set_columns()) == len(self.columns):
            self.refresh(all_columns=True)
        return {c: getattr(self, c) for c in self.get_set_columns()}


class HydraRenderNode(AbstractHydraTable):
    table_name = "hydra.render_nodes"
    if _UNIT_TEST:
        table_name = "test_" + table_name
    primary_key = 'id'
    _auto_column = 'id'
    columns = {'id', 'host', 'status', 'min_priority', 'platform', 'ip_addr', 'task_id', 'capabilities',
               'pulse', 'software_version', 'is_render_node'}

    id: int
    host: str
    status: (str, HydraStatus)
    min_priority: int
    platform: str
    ip_addr: str
    task_id: (int, None)
    capabilities: str
    pulse: datetime.datetime
    software_version: str
    is_render_node: int

    @classmethod
    def get_this_node(cls, explicit_transaction: Transaction = None) -> 'HydraRenderNode':
        """Return this host as a HydraRenderNode instance, None if not found.

        Args:
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            HydraRenderNode: Render node instance for this host, None if not found.

        """
        this_node = cls.fetch("WHERE host = %s", (hydra_utils.my_host_name(),),
                              explicit_transaction=explicit_transaction)
        return this_node[0] if this_node else None

    @classmethod
    def get_node_status_count(cls, nice_name: bool = False) -> list:
        """Return the status count as a list of tuples where [(count, status), (count, status)].

        Returns:
            list: List of tuples where [(count, status), (count, status)]

        """
        with Transaction() as t:
            t.cur.execute(f"SELECT count(status), status from {cls.table_name} GROUP BY status")
            status_counts = t.cur.fetchall()

        if nice_name:
            result = [(count, HydraStatus(status).nice_name) for (count, status) in status_counts]
        else:
            result = status_counts
        return result

    @property
    def task(self) -> 'HydraRenderTask':
        """Return the task running on the node or None of not active task.

        Returns:
            HydraRenderTask: Task object if one exists, None if not.

        """
        return self.get_task()

    def online(self) -> bool:
        """Set the node to Online and ready to accept tasks.

        Returns:
            bool: True if node is Online, False if error.

        """
        if self.status == HydraStatus.OFFLINE:
            return self.update_attr("status", HydraStatus.IDLE)
        elif self.status == HydraStatus.PENDING:
            return self.update_attr("status", HydraStatus.STARTED)
        else:
            logger.debug("No status changes made to %s", self.host)
            return True

    def offline(self) -> bool:
        """Set the node to Offline and not available to accept tasks.

        Returns:
            bool: True if node was set to Offline, False if error.

        """
        new_status = HydraStatus.PENDING if self.status == HydraStatus.STARTED else HydraStatus.OFFLINE
        new_status = new_status
        return self.update_attr("status", new_status)

    def get_off(self) -> bool:
        """Kill the current job and set Offline.

        Returns:
            bool: True if the job was killed and the node was offlined, False if not.

        """
        response = True
        if self.status == HydraStatus.STARTED:
            self.update_attr("status", HydraStatus.PENDING)
            task = self.get_task(["id", "status", "exit_code", "end_time", "host"])
            response = task.kill()

            if response:
                self.status = HydraStatus.OFFLINE
                self.task_id = None
                with Transaction() as t:
                    self.update(t)

        return response

    def kill_task(self, new_status: HydraStatus = HydraStatus.KILLED) -> bool:
        """Kill the current task running on this node.

        Args:
            new_status (str, HydraStatus): Status for the task after death, default HydraStatus.KILLED.

        Returns:
            bool: True if successful, False if not.

        """
        if self.status == HydraStatus.STARTED and self.task_id:
            task_obj = self.get_task(["host", "status", "exit_code", "end_time"])
            logger.debug("Killing task %d on %s", self.task_id, self.host)
            return task_obj.kill(new_status, True)
        else:
            logger.info("No task to kill on %s", self.host)
            return True

    def get_task(self, columns: Sequence = None, explicit_transaction: Transaction = None) -> 'HydraRenderTask':
        """Return a HydraRenderTask object for the current task running on this node. None if no task.

        Args:
            columns (Sequence): Sequence of columns to select.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            HydraRenderTask: Task object.

        """
        if self.task_id:
            return HydraRenderTask.fetch("WHERE id = %s", (self.task_id,), columns=columns,
                                         explicit_transaction=explicit_transaction)[0]

    def find_render_task(self) -> Union[Tuple['HydraRenderJob', 'HydraRenderTask'], Tuple[None, None]]:
        """Search the database for a render task for this host, return the Job and Task if they are found, or
        None, None if not.

        Returns:
            Union[Tuple['HydraRenderJob', 'HydraRenderTask'], Tuple[None, None]]: Job and Task if they are found, or
            None, None if not.

        """
        query = """SELECT T.*
                    FROM hydra.tasks T
                    JOIN
                        (SELECT id,
                                failed_nodes,
                                attempts,
                                max_attempts,
                                max_nodes,
                                requirements,
                                archived
                         FROM hydra.jobs) J ON (T.job_id = J.id)
                    WHERE T.status = %s
                        AND J.archived = 0
                        AND T.priority > %s
                        AND J.max_attempts > J.attempts
                        AND J.failed_nodes NOT LIKE %s
                        AND %s LIKE J.requirements
                    ORDER BY T.priority DESC,
                             T.id ASC
                    LIMIT 1;"""

        args = (HydraStatus.READY.value, self.min_priority, f'%{self.host}%', self.capabilities)

        with Transaction() as t:
            logger.debug("Checking for tasks")
            task = self._do_fetch(t, query, args)
            if task:
                task = HydraRenderTask(task[0])
                logger.debug("RenderTask found %s", task)
                job = task.get_job()
                # Task Updates
                task.status = HydraStatus.STARTED
                task.host = self.host
                task.start_time = datetime.datetime.now().replace(microsecond=0)
                # Job Updates
                job.status = HydraStatus.STARTED
                # Node Updates
                self.status = HydraStatus.STARTED
                self.task_id = task.id
                # Push updates to the db
                task.update(t)
                job.update(t)
                self.update(t)
                return job, task

        return None, None

    def unstick_task(self, new_status=HydraStatus.READY):
        """Unstick a task that was stuck on a node. This runs when the node starts up and discovers it has a job
        assigned to it but has no memory of the job running.

        Args:
            new_status (HydraStatus): The status to set the task to.

        """
        self.refresh()
        with Transaction() as t:
            if self.status in STUCK_STATUS:
                # Set node status to IDLE if the job was running, else OFFLINE
                self.status = HydraStatus.IDLE if self.status == HydraStatus.STARTED else HydraStatus.OFFLINE

            task = self.get_task()
            if task:
                task.status = new_status
                task.end_time = datetime.datetime.now().replace(microsecond=0)
                task.exit_code = 999
                task.update(t)

            self.task_id = None
            self.update(t)


class HydraRenderJob(AbstractHydraTable):
    table_name = "hydra.jobs"
    if _UNIT_TEST:
        table_name = 'test_' + table_name
    primary_key = 'id'
    _auto_column = 'id'
    columns = {'id', 'name', 'owner', 'status', 'creation_time', 'requirements', 'args', 'task_file',
               'priority', 'max_nodes', 'timeout', 'failed_nodes', 'attempts', 'max_attempts', 'archived', 'task_total',
               'task_done', 'start_frame', 'end_frame', 'by_frame', 'render_layers', 'mpf', 'output_directory',
               'project', 'script', 'mode'}

    id: int
    name: str
    owner: str
    status: (str, HydraStatus)
    creation_time: datetime.datetime
    requirements: str
    args: str
    task_file: str
    priority: int
    max_nodes: int
    timeout: int
    failed_nodes: str
    attempts: int
    max_attempts: int
    archived: int
    task_total: int
    task_done: int
    start_frame: int
    end_frame: int
    by_frame: int
    render_layers: str
    mpf: (datetime.time, None)
    output_directory: str
    project: str
    script: str
    mode: str

    def get_tasks(self, columns: Sequence = None, explicit_transaction: Transaction = None) -> List['HydraRenderTask']:
        """Return a list of tasks for the job.

        Args:
            columns (Sequence): Sequence of columns to select.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            List[HydraRenderTask]: List of tasks for the job.

        """
        return HydraRenderTask.fetch("WHERE job_id = %s", (self.id,), columns=columns,
                                     explicit_transaction=explicit_transaction)

    def start(self) -> bool:
        """Set the job status to Ready To Start.

        Returns:
            bool: True if successful, False if job is not Paused or Killed before trying.

        """
        if self.status in [HydraStatus.PAUSED, HydraStatus.KILLED]:
            self.status = HydraStatus.READY
            task_list = self.get_tasks(["status"])
            with Transaction() as t:
                self.update(t)
                for task in task_list:
                    if task.status in [HydraStatus.PAUSED, HydraStatus.KILLED]:
                        task.status = HydraStatus.READY
                        task.update(t)
            return True
        return False

    def pause(self) -> bool:
        """Pause the job and set all tasks to Paused.

        Returns:
            bool: True if successful, False if job is not Ready or Killed before trying.

        """
        if self.status in [HydraStatus.READY, HydraStatus.KILLED]:
            self.status = HydraStatus.PAUSED
            task_list = self.get_tasks(["status"])
            with Transaction() as t:
                self.update(t)
                for task in task_list:
                    if task.status in [HydraStatus.READY, HydraStatus.KILLED]:
                        task.status = HydraStatus.PAUSED
                        task.update(t)
            return True
        return False

    def kill(self, new_status: HydraStatus = HydraStatus.KILLED, tcp_kill: bool = True) -> List:
        """Kill the job and set all tasks to Killed.

        Args:
            new_status (HydraStatus): Status to set the job and tasks to after death.
            tcp_kill (bool): If True will attempt a TCP connection to the node to kill the task. Default True.

        Returns:
            list: A list of responses from the tasks/nodes.

        """
        tasks = self.get_tasks(["id", "status", "exit_code", "end_time", "host"])
        responses = [task.kill(new_status, tcp_kill) for task in tasks]
        responses += [self.update_attr("status", new_status)]
        for task in tasks:
            if task.status != HydraStatus.FINISHED:
                responses += [task.update_attr("status", new_status)]

        return responses

    def reset(self):
        """Reset this job and all of it's tasks.

        Returns:
            None

        """
        columns = ["status", "mpf", "host", "start_time", "end_time", "exit_code"]
        task_list = self.get_tasks(columns)
        self.status = HydraStatus.PAUSED
        self.mpf = None
        self.attempts = 0
        self.failed_nodes = ""
        for task in task_list:
            task.status = HydraStatus.PAUSED
            task.mpf = None
            task.host = None
            task.start_time = None
            task.end_time = None
            task.exit_code = None
        with Transaction() as t:
            self.update(t)
            [task.update(t) for task in task_list]

    def reset_failed_nodes(self):
        """Reset this job's failed nodes list.

        Returns:
            None

        """
        self.failed_nodes = ""
        self.update()

    def archive(self, mode: Any) -> bool:
        """Set the job to Archived so it does not show up in FarmView.

        Args:
            mode (Any): bool, int, str, etc.

        Returns:
            bool: True if the archive was successful, False if not.

        """
        if not isinstance(mode, int):
            mode = 1 if str(mode).lower().startswith("t") else 0
        return self.update_attr("archived", mode)

    def prioritize(self, priority: int) -> bool:
        """Updates the priority for the job to the given priority.

        Args:
            priority (int): New priority.

        Returns:
            bool: True if the update was successful, False if not.

        """
        return self.update_attr("priority", priority)
    
    def update_job_status(self, failed_node: str = None, mpf: datetime.timedelta = None):
        """Update this job's status field based on the statuses of the child tasks. Args are used for updates
        when a render task is complete.

        Args:
            failed_node (str): Optionally add a failed node to the fail list and iterate on the attempt field.
            mpf (datetime.timedelta): Optionally update the minutes per frame timedelta field.

        """
        task_list = self.get_tasks(('status',))  # Should all of these counts be done by the SQL server?

        with Transaction() as t:
            self.refresh(explicit_transaction=t)
            self.task_done = len([task for task in task_list if task.status == HydraStatus.FINISHED])

            if failed_node:
                self.attempts += 1
                self.failed_nodes += f"{failed_node} "

            if self.attempts >= self.max_attempts:
                self.status = HydraStatus.ERROR
            else:
                if all([task.status == HydraStatus.FINISHED for task in task_list]):
                    self.status = HydraStatus.FINISHED
                elif any([task.status == HydraStatus.STARTED for task in task_list]):
                    self.status = HydraStatus.STARTED
                elif any([task.status == HydraStatus.READY for task in task_list]):
                    self.status = HydraStatus.READY
                elif any([task.status == HydraStatus.ERROR for task in task_list]):
                    self.status = HydraStatus.ERROR
                else:
                    self.status = HydraStatus.PAUSED

            if mpf is not None:
                if self.mpf is not None:
                    self.mpf = ((self.mpf + mpf) / 2)
                else:
                    self.mpf = mpf

            self.update(explicit_transaction=t)


class HydraRenderTask(AbstractHydraTable):
    table_name = "hydra.tasks"
    if _UNIT_TEST:
        table_name = 'test_' + table_name
    primary_key = 'id'
    _auto_column = 'id'
    columns = {'id', 'job_id', 'status', 'priority', 'host', 'start_frame', 'end_frame', 'exit_code', 'start_time',
               'end_time', 'mpf'}

    id: int
    job_id: int
    status: (str, HydraStatus)
    priority: int
    host: (str, None)
    start_frame: int
    end_frame: int
    exit_code: (int, None)
    start_time: (datetime.datetime, None)
    end_time: (datetime.datetime, None)
    mpf: (datetime.time, None)

    def get_job(self, columns: Sequence = None, explicit_transaction: Transaction = None) -> 'HydraRenderJob':
        """Return job object for the task.

        Args:
            columns (Sequence): Sequence of columns to select.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            HydraRenderJob: Job object for the task.

        """
        return HydraRenderJob.fetch("WHERE id = %s", (self.job_id,), columns=columns,
                                    explicit_transaction=explicit_transaction)[0]

    def get_host(self, columns: Sequence = None, explicit_transaction: Transaction = None) -> 'HydraRenderNode':
        """Return host object for the task.

        Args:
            columns (Sequence): Sequence of columns to select.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            HydraRenderNode: Render node object for the task, None if no render node on task.

        """
        if self.host:
            return HydraRenderNode.fetch("WHERE host = %s", (self.host,), columns=columns,
                                         explicit_transaction=explicit_transaction)[0]

    def get_other_subtasks(self, columns: Sequence = None,
                           explicit_transaction: Transaction = None) -> List['HydraRenderTask']:
        """Return all sibling tasks.

        Args:
            columns (Sequence): Sequence of columns to select.
            explicit_transaction (Transaction): An explicit DB transaction or None. Default None.

        Returns:
            List[HydraRenderTask]: List of sibling task objects.

        """
        return HydraRenderTask.fetch("WHERE job_id = %s AND id != %s", (self.job_id, self.id), columns=columns,
                                     explicit_transaction=explicit_transaction)

    def start(self) -> bool:
        """Set the task status to Ready To Start, making it available for a node to pick up.

        Returns:
            bool: True if successful, False if not.

        """
        if self.status in [HydraStatus.PAUSED, HydraStatus.KILLED]:
            job = self.get_job(["status"])
            self.status = HydraStatus.READY
            with Transaction() as t:
                self.update(t)
                if job.status in [HydraStatus.PAUSED, HydraStatus.KILLED]:
                    job.status = HydraStatus.READY
                    job.update(t)
            return True
        return False

    def pause(self) -> bool:
        """Set the task to Paused, making it unavailable for nodes to pickup but not killing it.

        Returns:
            bool: True if successful, False if not.

        """
        if self.status in [HydraStatus.READY, HydraStatus.KILLED]:
            job = self.get_job(["status"])
            self.status = HydraStatus.PAUSED
            with Transaction() as t:
                self.update(t)
                if job.status in [HydraStatus.READY, HydraStatus.KILLED]:
                    job.status = HydraStatus.PAUSED
                    job.update(t)
            return True
        return False

    def kill(self, new_status: HydraStatus = HydraStatus.KILLED, tcp_kill: bool = True) -> bool:
        """Kill the task and set it to Killed.

        Args:
            new_status (str, HydraStatus): Status to set the task to after it's been killed.
            tcp_kill (bool): If True will attempt to make a TCP connection to the node to kill the task.

        Returns:
            bool: True if successful, False if not.

        """
        if self.status == HydraStatus.STARTED:
            killed = False
            update_node = True
            node = self.get_host(["status", "task_id"])

            if tcp_kill:
                if node.task_id != self.id:
                    logger.warning("Node is not running the given task! Marking as dead.")
                    update_node = False

                else:
                    killed = self.send_kill_question(new_status)
                    # If killed returns None then the node is probably offline
                    if killed:
                        return killed.err

            # If it was not killed by the node then we need to mark it as dead
            # here instead
            if not killed:
                logger.debug("tcp_kill received None, marking task as killed")
                self.status = new_status
                self.exit_code = 1
                self.end_time = datetime.datetime.now()
                with Transaction() as t:
                    self.update(t)
                    if update_node:
                        node.status = HydraStatus.IDLE if node.status == HydraStatus.STARTED else HydraStatus.OFFLINE
                        node.task_id = None
                        node.update(t)
                return True
        else:
            logger.debug("Task Kill is skipping task %s because of status %s", self.id, self.status)
            return True

    def reset(self) -> bool:
        """Reset the task.

        Returns:
            bool: True if successful, False if not.

        """
        if self.status != HydraStatus.STARTED:
            job = self.get_job(["status"])
            other_tasks = self.get_other_subtasks(["status"])
            status_check = any([task.status == HydraStatus.STARTED for task in other_tasks])
            self.status = HydraStatus.PAUSED
            self.mpf = None
            self.host = None
            self.start_time = None
            self.end_time = None
            self.exit_code = None
            with Transaction() as t:
                self.update(t)
                if job.status == HydraStatus.KILLED and not status_check:
                    job.status = HydraStatus.PAUSED
                    job.update(t)
            return True
        return False

    def send_kill_question(self, new_status: HydraStatus) -> HydraResponse:
        """Make a TCP connection to the host for the task and ask it to kill the task.

        Args:
            new_status (str, HydraStatus): Status to set the task to after it's been killed.

        Returns:
            bool: True if successful, False if not.

        """
        logger.debug('Kill task on %s', self.host)
        node = self.get_host(["ip_addr"])
        port = int(_config['networking']['host_port'])
        request = HydraRequest.from_args('kill_current_task', args=(new_status,))
        response = send_request(node.ip_addr, port, request)
        if response.msg.startswith('TimeoutError'):
            logger.debug("%s appears to be offline or unresponsive. Treating as dead.", self.host)
        else:
            logger.debug("Child killed return msg '%s' for node '%s'", response.msg, self.host)
            if response.err:
                logger.warning("%s tried to kill its job but failed for some reason.", self.host)

        return response

    def create_task_cmd(self, hydra_job: 'HydraRenderJob') -> Union[str, list, None]:
        """Return the task command used to launch the task.

        Args:
            hydra_job (HydraRenderJob): Job object for the task.

        Returns:
            str, list: String or list used to launch the task.

        """
        if hydra_job.mode == "Maya Render":
            task_file = os.path.normpath(hydra_job.task_file)
            base_cmd = shlex.split(hydra_job.args, posix=False)
            cmd = ['render']
            cmd += base_cmd

            cmd += ["-s", self.start_frame, "-e", self.end_frame, "-rl", hydra_job.render_layers,
                    '-proj', hydra_job.project]

            if hydra_job.output_directory:
                frame_dir = os.path.normpath(hydra_job.output_directory)
                cmd += ["-rd", frame_dir]

            cmd += [task_file]

        elif hydra_job.mode == 'MayaPy':
            cmd = ['mayapy', '-c', hydra_job.script]

        elif hydra_job.mode == 'Command':
            cmd = shlex.split(hydra_job.script, posix=False)

        else:
            logger.error("Bad Job Type!")
            return None

        return [str(x) for x in cmd]

    def get_log_path(self) -> pathlib.Path:
        """Return the path to the log file for the task.

        Returns:
            pathlib.Path: Path object pointing to the log file.

        """
        this_host = hydra_utils.my_host_name()
        render_log_dir = _config['logs']['render_log_path']
        path = pathlib.Path(render_log_dir, f'{self.id:0>10}.log.txt')
        if self.host and this_host == self.host:
            return path
        elif self.host:
            path = pathlib.Path(f'//{self.host}', str(path).replace(path.drive, ''))
            return path


class HydraCapabilities(AbstractHydraTable):
    table_name = "hydra.capabilities"
    if _UNIT_TEST:
        table_name = 'test_' + table_name
    primary_key = 'name'
    _auto_column = None
    columns = {'name'}
    name: str
