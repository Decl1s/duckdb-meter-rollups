-- Я не позволяю автоопределению CSV превратить идентификатор или деньги в иной тип.
SELECT count(*) FROM incoming WHERE
    event_id IS NULL OR NOT regexp_full_match(event_id, '[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
 OR site_id IS NULL OR NOT regexp_full_match(site_id, '[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
 OR meter_id IS NULL OR NOT regexp_full_match(meter_id, '[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
 OR occurred_at IS NULL OR NOT regexp_full_match(occurred_at, '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
 OR try_strptime(occurred_at, '%Y-%m-%dT%H:%M:%SZ') IS NULL
 OR substr(occurred_at, 1, 4) NOT BETWEEN '2000' AND '2099'
 OR energy_wh IS NULL OR NOT regexp_full_match(energy_wh, '0|[1-9][0-9]{0,9}')
 OR try_cast(energy_wh AS BIGINT) IS NULL OR try_cast(energy_wh AS BIGINT) > 1000000000;
