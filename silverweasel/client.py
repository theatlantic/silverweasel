from os.path import basename
from pkg_resources import resource_string, resource_exists
import logging

from zeep import Client
from zeep.transports import Transport
import arrow

from silverweasel.sftp import SFTPClient
from silverweasel.utils import parse_datetime

logger = logging.getLogger(__name__)


class FixedSliverPoopWSDL:
    def add(self, url, content):
        pass

    # pylint: disable=no-self-use
    def get(self, url):
        fname = "data/%s" % basename(url)
        if resource_exists(__name__, fname):
            return resource_string(__name__, fname)
        return None


class SilverClient:
    def __init__(self, pod, username, password, timezone='America/New_York'):
        self.pod = str(pod)
        self.username = username
        self.password = password
        self.timezone = timezone
        self.login()

    def parse_datetime(self, parseable):
        return parse_datetime(parseable, self.timezone)

    def login(self):
        wsdl = "http://api%s.ibmmarketingcloud.com/SoapApi?wsdl" % self.pod
        transport = Transport(cache=FixedSliverPoopWSDL())
        self.client = Client(wsdl, transport=transport)
        self.headers = None
        logger.debug('Authenticating using config from %s', wsdl)
        response = self._call('Login',
                              USERNAME=self.username,
                              PASSWORD=self.password)
        self.headers = {'sessionidheader': response['SESSIONID']}

    def _call(self, method, **kwargs):
        # keep it clean for debugging logs, no user/pass
        ckwargs = kwargs.copy() if method != 'Login' else '<redacted>'
        logger.debug('Calling SOAP function "%s" with %s', method, ckwargs)

        kwargs['_soapheaders'] = self.headers
        response = getattr(self.client.service, method)(**kwargs)
        if not response['SUCCESS']:
            # handle expired session
            if response['Fault']['detail']['error']['errorid'] == '145':
                logger.warning('Restarting expired session')
                self.login()
                return self._call(method, **kwargs)
            errmsg = "Error calling %s: %s" % (method, response)
            logger.error(errmsg)
            raise RuntimeError(errmsg)
        return response

    def get_list_mailings(self, list_id, startdate, enddate=None):
        """
        startdate and enddate should be an Arrow object
        """
        startdate = startdate.format('MM/DD/YYYY HH:mm:ss')
        enddate = enddate if enddate else arrow.now(self.timezone)
        enddate = enddate.format('MM/DD/YYYY HH:mm:ss')
        response = self._call('GetSentMailingsForList',
                              LIST_ID=list_id,
                              DATE_START=startdate,
                              DATE_END=enddate,
                              INCLUDE_CHILDREN=1)
        return response['Mailing']

    def get_job_status(self, job_id):
        return self._call('GetJobStatus', JOB_ID=job_id)

    def get_contact_lists(self):
        # per https://ibm.co/2optFbt - list type 18 is contact lists
        return self.get_lists(18)

    def get_suppression_lists(self):
        # per https://ibm.co/2optFbt - list type 13 is suppression lists
        return self.get_lists(13)

    def get_databases(self):
        # per https://ibm.co/2optFbt - list type 0 is databases
        return self.get_lists(0)

    def get_lists(self, list_type):
        """
        List types can be found at https://ibm.co/2optFbt
        """
        response = self._call('GetLists',
                              VISIBILITY=1,
                              INCLUDE_ALL_LISTS=True,
                              LIST_TYPE=list_type)
        flist = FolderList()
        folders = [item for item in response['LIST'] if item['IS_FOLDER']]
        for folder in folders:
            flist.add(folder['ID'], folder['NAME'], folder['PARENT_FOLDER_ID'])
        clists = [li for li in response['LIST'] if not li['IS_FOLDER']]
        for item in clists:
            item['FOLDER_PATH'] = flist.get_path(item['PARENT_FOLDER_ID'])
            item['LAST_MODIFIED'] = self.parse_datetime(item['LAST_MODIFIED'])
        return clists

    def export_list(self, list_id, startdate=None, enddate=None, export="ALL"):
        """
        startdate and enddate should be arrow.Arrow objects for time, or None.
        export should be one of ALL, OPT_IN, OPT_OUT, or UNDELIVERABLE
        """
        kwargs = {
            'LIST_ID': list_id,
            'EXPORT_TYPE': export,
            'FILE_ENCODING': 'UTF-8',
            'EXPORT_FORMAT': 'CSV'
        }
        if startdate:
            kwargs['DATE_START'] = startdate.format('MM/DD/YYYY HH:mm:ss')
        if enddate:
            kwargs['DATE_END'] = enddate.format('MM/DD/YYYY HH:mm:ss')
        response = self._call('ExportList', **kwargs)
        return ExportJob(self, response)

    def export_raw_list_events(self, list_id, startdate=None, enddate=None):
        if startdate:
            startdate = startdate.format('MM/DD/YYYY HH:mm:ss')
        if enddate:
            enddate = enddate.format('MM/DD/YYYY HH:mm:ss')
        return self._export_raw(LIST_ID=list_id,
                                EVENT_DATE_START=startdate,
                                EVENT_DATE_END=enddate)

    def export_raw_mailing_events(self, mailing_id, startdate=None,
                                  enddate=None):
        if startdate:
            startdate = startdate.format('MM/DD/YYYY HH:mm:ss')
        if enddate:
            enddate = enddate.format('MM/DD/YYYY HH:mm:ss')
        return self._export_raw(MAILING_ID=mailing_id,
                                EVENT_DATE_START=startdate,
                                EVENT_DATE_END=enddate)

    def _export_raw(self, **kwargs):
        """
        Private - should only be called internally because all kwargs are
        expected to be ready to be sent up as is (for instance, dates
        formatted, etc).
        """
        kwargs['MOVE_TO_FTP'] = 1
        kwargs['FILE_ENCODING'] = kwargs.get('FILE_ENCODING', 'UTF-8')
        response = self._call('RawRecipientDataExport', **kwargs)
        return ExportJob(self, response['MAILING'])

    def connect_sftp(self):
        logger.debug("Connecting to SFTP server for pod %s", self.pod)
        return SFTPClient(self.pod, self.username, self.password)


class FolderList:
    def __init__(self):
        self.folders = {}

    def add(self, fid, name, parent_id):
        self.folders[fid] = (name, parent_id)

    def get_path(self, fid):
        if fid not in self.folders:
            return []
        name, parent_id = self.folders[fid]
        return self.get_path(parent_id) + [name]


class ExportJob:
    def __init__(self, client, result):
        self.client = client
        self.result = result

    def get_status(self):
        result = self.client.get_job_status(self.result['JOB_ID'])
        return result['JOB_STATUS']

    def is_complete(self):
        return self.get_status() == 'COMPLETE'

    def get_result_path(self):
        return self.result['FILE_PATH']
