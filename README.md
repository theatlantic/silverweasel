# silverweasel
[![Build Status](https://secure.travis-ci.org/theatlantic/silverweasel.png?branch=master)](https://travis-ci.org/theatlantic/silverweasel)

A python library for working with the IBM Silverpop API.  It handles all of the inanity of things like connecting to SFTP to get export files (including handling unzipping when necessary, etc).


## Example Usage
```python
import time
import arrow
from silverweasel.client import SilverClient

client = SilverClient(5, "username", "password")

# get some contact lists
clists = client.get_contact_lists()
for clist in clists:
    print(clist)

# export a client list and print it
job = client.export_list(clists[0]['ID'])
while not job.is_complete():
    print(job.get_status())
    time.sleep(1)

with client.connect_sftp() as sftp:
    with sftp.open_job_result(job) as f:
        print(f.read())
    sftp.remove_job_result(job)

# get all mailings for a list in the last 3 days
mailings = client.get_list_mailings(clists[0]['ID'], arrow.utcnow().shift(days=-3))
print(mailings)

# Print all of the individual mailing events for a specific mailing
last_mailing_id = mailings[0]['MailingId']
job = client.export_raw_mailing_events(last_mailing_id)

while not job.is_complete():
    print(job.get_status())
    time.sleep(1)

with client.connect_sftp() as sftp:
    with sftp.open_job_result(job) as f:
        print(f.read())
    sftp.remove_job_result(job)
```

## Logging
This library uses the standard [Python logging library](https://docs.python.org/3/library/logging.html).  To see debut output printed to STDOUT, for instance, use:

```python
import logging

log = logging.getLogger('silverweasel')
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())
```

## Running Tests
To run tests:

```
pip install -r dev-requirements.txt
python -m unittest
```