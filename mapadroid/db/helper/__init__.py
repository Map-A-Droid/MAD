from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.helper.SettingsRoutecalcHelper import SettingsRoutecalcHelper
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)

valid_area_modes = {"idle", "iv_mitm", "mon_mitm", "pokestops", "raids_mitm"}


async def fix_routecalc(session: AsyncSession) -> None:
    # TODO: Proper SQLAlchemy usage...
    # nested_select = select(SettingsArea, ).select_from(SettingsArea)
    rc_sql = "IFNULL(id.`routecalc`, IFNULL(iv.`routecalc`, IFNULL(mon.`routecalc`, " \
             "IFNULL(ps.`routecalc`, ra.`routecalc`))))"
    sql = "SELECT a.`area_id`, a.`instance_id` AS 'ain', rc.`routecalc_id`, rc.`instance_id` AS 'rcin' " \
          "FROM (" \
          " SELECT sa.`area_id`, sa.`instance_id`, %s AS 'routecalc' " \
          " FROM `settings_area` sa " \
          " LEFT JOIN `settings_area_idle` id ON id.`area_id` = sa.`area_id`" \
          " LEFT JOIN `settings_area_iv_mitm` iv ON iv.`area_id` = sa.`area_id`" \
          " LEFT JOIN `settings_area_mon_mitm` mon ON mon.`area_id` = sa.`area_id`" \
          " LEFT JOIN `settings_area_pokestops` ps ON ps.`area_id` = sa.`area_id`" \
          " LEFT JOIN `settings_area_raids_mitm` ra ON ra.`area_id` = sa.`area_id`" \
          ") a " \
          "INNER JOIN `settings_routecalc` rc ON rc.`routecalc_id` = a.`routecalc` " \
          "WHERE a.`instance_id` != rc.`instance_id`" % (rc_sql,)
    result = await session.execute(text(sql))
    bad_entries = result.scalars().all()
    if bad_entries:
        logger.info('Routecalcs with mis-matched IDs present. {}', bad_entries)
        for _area_id, ain, routecalc_id, _rcin in bad_entries:
            await SettingsRoutecalcHelper.update_instance_id(session, routecalc_id, ain)
