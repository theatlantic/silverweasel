import datetime
import arrow


def parse_datetime(parseable, timezone):
    """
    Turn a string (silverpop uses multiple datetime formats, we'll
    try to figure out which one we're given) or a datetime.datetime
    into an arrow.Arrow object for sane date interaction.
    """
    if isinstance(parseable, datetime.datetime):
        return arrow.get(parseable, timezone)
    if '.' in parseable:
        # parseable is like '2017-12-21 14:00:05.0'
        dformat = 'YYYY-MM-DD HH:mm:ss.S'
    elif len(parseable.split(' ')) == 2:
        # parseable is like '12/21/2017 20:49:58'
        dformat = 'MM/DD/YYYY HH:mm:ss'
    elif len(parseable.split(' ')[0].split('/')[2]) == 2:
        # parseable is like '12/21/17 14:00 PM
        dformat = 'MM/DD/YY HH:mm A'
    elif parseable[6:8] == "00":
        # parseable is like '12/21/0017 14:00 PM, presumably
        # because what was meant was 2017 but what was given was '17'
        # which sliverpoop interprets as the year '0017'
        parseable = parseable[:6] + '2' + parseable[7:]
        dformat = 'MM/DD/YYYY HH:mm A'
    else:
        # parseable is like '12/21/2017 14:00 PM'
        dformat = 'MM/DD/YYYY HH:mm A'
    return arrow.get(parseable, dformat, tzinfo=timezone)
