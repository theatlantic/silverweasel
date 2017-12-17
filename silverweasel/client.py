from os.path import basename
from pkg_resources import resource_string, resource_exists

from zeep import Client
from zeep.transports import Transport
import arrow

from silverweasel.sftp import SFTPClient


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
        self.pod = pod
        self.username = username
        self.password = password
        self.timezone = timezone
        self.login()

    def login(self):
        wsdl = "http://api%i.ibmmarketingcloud.com/SoapApi?wsdl" % self.pod
        transport = Transport(cache=FixedSliverPoopWSDL())
        self.client = Client(wsdl, transport=transport)
        self.headers = None
        response = self._call('Login',
                              USERNAME=self.username,
                              PASSWORD=self.password)
        self.headers = {'sessionidheader': response['SESSIONID']}

    def _call(self, method, **kwargs):
        kwargs['_soapheaders'] = self.headers
        response = getattr(self.client.service, method)(**kwargs)
        if not response['SUCCESS']:
            errmsg = "Error calling %s: %s" % (method, response)
            raise RuntimeError(errmsg)
        return response

    def get_list_mailings(self, list_id, startdate, enddate=None):
        """
        startdate and enddate should be an Arrow object
        """
        enddate = enddate if enddate else arrow.now(self.timezone)
        startdate = startdate.format('MM/DD/YYYY HH:mm:ss')
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
            dformat = 'MM/DD/YY HH:mm a'
            item['LAST_MODIFIED'] = arrow.get(item['LAST_MODIFIED'], dformat)
        return clists

    def export_list(self, list_id):
        response = self._call('ExportList',
                              LIST_ID=list_id,
                              EXPORT_TYPE="ALL",
                              EXPORT_FORMAT="CSV")
        return ExportJob(self, response)

    def export_raw_list_events(self, list_id):
        return self.export_raw(LIST_ID=list_id)

    def export_raw_mailing_events(self, mailing_id):
        return self.export_raw(MAILING_ID=mailing_id)

    def export_raw(self, **kwargs):
        kwargs['MOVE_TO_FTP'] = 1
        response = self._call('RawRecipientDataExport', **kwargs)
        return ExportJob(self, response['MAILING'])

    def connect_sftp(self):
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
