import asyncio
import datetime
import gc
import os
from calendar import calendar
from threading import active_count

import psutil

from mapadroid.db.helper.TrsUsageHelper import TrsUsageHelper
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import application_args, terminate_mad

logger = get_logger(LoggerEnums.system)


def find_referring_graphs(obj):
    ignore_elems = [locals(), globals(), gc.garbage]

    referrers = (r for r in gc.get_referrers(obj) if r not in ignore_elems)
    for ref in referrers:
        print(type(ref))
        if isinstance(ref, Graph):  # noqa: F821
            # A graph node
            yield ref
        elif isinstance(ref, dict):
            # An instance or other namespace dictionary
            for parent in find_referring_graphs(ref):
                yield parent


async def get_system_infos(db_wrapper):
    pid = os.getpid()
    process_running = psutil.Process(pid)
    gc.set_threshold(5, 1, 1)
    gc.enable()
    await asyncio.sleep(60)
    if application_args.trace:
        import tracemalloc
        tracemalloc.start(5)
    while not terminate_mad.is_set():
        logger.debug('Starting internal Cleanup')
        loop = asyncio.get_running_loop()
        collected, cpu_usage, mem_usage, unixnow = await loop.run_in_executor(
            None, __run_system_stats, process_running)
        async with db_wrapper as session, session:
            await TrsUsageHelper.add(session, application_args.status_name, cpu_usage, mem_usage, collected, unixnow)
            await session.commit()
        await asyncio.sleep(application_args.statistic_interval)


last_snapshot = None
initial_snapshot = None


def display_top(snapshot, key_type='traceback', limit=30):
    import tracemalloc
    import linecache
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    logger.info("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        logger.info("#%s: %s:%s: %.1f KiB"
                    % (index, frame.filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            logger.info('    %s' % line)
            logger.info(stat.traceback.format(10))

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        logger.info("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    logger.info("Total allocated size: %.1f KiB" % (total / 1024))


def __run_system_stats(py):
    global last_snapshot, initial_snapshot
    logger.debug('Collecting...')
    unreachable_objs = gc.collect()
    logger.debug('Unreachable objects: {} - Remaining garbage: {} - Running threads: {}',
                 str(unreachable_objs), str(gc.garbage), str(active_count()))
    for obj in gc.garbage:
        for ref in find_referring_graphs(obj):
            ref.set_next(None)
            del ref  # remove local reference so the node can be deleted
        del obj  # remove local reference so the node can be deleted

    # Clear references held by gc.garbage
    logger.debug('Clearing gc garbage')
    del gc.garbage[:]
    mem_usage = py.memory_info()[0] / 2. ** 30
    cpu_usage = py.cpu_percent()
    logger.info('Instance name: "{}" - Memory usage: {:.3f} GB - CPU usage: {}',
                str(application_args.status_name), mem_usage, str(cpu_usage))
    collected = None
    if application_args.stat_gc:
        collected = gc.collect()
        logger.debug("Garbage collector: collected %d objects." % collected)
    zero = datetime.datetime.utcnow()
    unixnow = calendar.timegm(zero.utctimetuple())

    if application_args.trace:
        import tracemalloc
        new_snapshot = tracemalloc.take_snapshot()
        if last_snapshot:

            try:
                display_top(new_snapshot)
            except Exception as e:
                logger.exception(e)
            top_stats = new_snapshot.compare_to(last_snapshot, 'traceback')
            logger.info("Top of diff")
            for stat in top_stats[:15]:
                logger.info(stat)
                logger.info(stat.traceback.format(15))
            logger.info("Bottom of diff")
            for stat in top_stats[-15:]:
                logger.info(stat)
            if not initial_snapshot:
                initial_snapshot = new_snapshot

            top_stats_to_initial = new_snapshot.compare_to(initial_snapshot, 'traceback')
            logger.info("Top of diff to initial")
            for stat in top_stats_to_initial[:15]:
                logger.info(stat)
                logger.info(stat.traceback.format(15))
            logger.info("Bottom of diff to initial")
            for stat in top_stats_to_initial[-15:]:
                logger.info(stat)
        last_snapshot = new_snapshot

    try:
        import objgraph
        logger.info("show_most_common_types")
        objgraph.show_most_common_types(limit=50, shortnames=False)
        logger.info("show_growth")
        objgraph.show_growth(limit=50, shortnames=False)
        logger.info("get_new_ids")
        objgraph.get_new_ids(limit=50)
        logger.info("Constructing backrefs graph")
        # by_type = objgraph.by_type('builtins.list')
        by_type = objgraph.by_type('StackSummary')
        # by_type = objgraph.by_type('uvloop.Loop')
        # by_type = objgraph.by_type("mapadroid.utils.collections.Location")
        # by_type = objgraph.by_type("TrsSpawn")
        if len(by_type) > 1:
            by_type_empty = [type_filtered for type_filtered in by_type if not type_filtered]
            # by_type_filled = [type_filtered for type_filtered in by_type if type_filtered and "mapadroid" in type_filtered.filename]
            by_type_filled = [type_filtered for type_filtered in by_type if type_filtered]
            logger.warning("Filled: {}, empty: {}, total: {}", len(by_type_filled), len(by_type_empty),
                           len(by_type))
            obj = by_type[-500:]
            # TODO: Filter for lists of dicts...
            # filtered = [type_filtered for type_filtered in by_type if len(type_filtered) > 50]
            del by_type_empty
            del by_type_filled
            del by_type
            # objgraph.show_backrefs(obj, max_depth=10)
            # objgraph.show_backrefs(obj, max_depth=5)
        else:
            logger.warning("Not enough of type to show: {}", len(by_type))
    except Exception as e:
        pass
    logger.info("Done with GC")
    return collected, cpu_usage, mem_usage, unixnow
