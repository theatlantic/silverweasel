from zipfile import ZipFile
import paramiko


class SFTPClient:
    def __init__(self, pod, username, password):
        self.host = "transfer%i.ibmmarketingcloud.com" % pod
        self.username = username
        self.password = password
        self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def connect(self):
        transport = paramiko.Transport((self.host, 22))
        transport.connect(username=self.username, password=self.password)
        self.client = paramiko.SFTPClient.from_transport(transport)
        # sometimes silverpop gives relative paths, sometimes it doesn't.
        # For the cases where it doesn't, usually we're looking for files in
        # the /download directory.  Thanks Silverpop!
        self.client.chdir('/download')

    def disconnect(self):
        channel = self.client.get_channel()
        channel.get_transport().close()
        self.client = None

    def listdir(self, path='.'):
        return self.client.listdir(path)

    def exists(self, path):
        try:
            self.client.lstat(path)
            return True
        except FileNotFoundError:
            return False

    def remove_job_result(self, job):
        path = job.get_result_path()
        if not job.is_complete() or not self.exists(path):
            msg = "Job not completed or errored or results already deleted."
            raise FileNotFoundError(msg)
        return self.remove(path)

    def remove(self, path):
        return self.client.remove(path)

    def open_job_result(self, job, zipname=None):
        """
        job should be a ExportJob
        """
        if not job.is_complete():
            raise FileNotFoundError("Job not completed yet or errored.")
        path = job.get_result_path()
        if path.endswith('.zip'):
            return RemoteZipFile(self.client, path, zipname, 'r')
        return RemoteFile(self.client, path, 'r')


# pylint: disable=too-few-public-methods
class RemoteFile:
    def __init__(self, client, path, mode):
        self.client = client
        self.path = path
        self.mode = mode
        self.file = None

    def __enter__(self):
        self.file = self.client.open(self.path, self.mode)
        return self.file

    def __exit__(self, *args):
        self.file.close()


class RemoteZipFile(RemoteFile):
    def __init__(self, client, path, fname, mode):
        if mode != 'r':
            raise RuntimeError('Only read mode support for zip files')
        super().__init__(client, path, mode)
        self.fname = fname
        self.file = None
        self.innerzip = None
        self.zip = None

    def __enter__(self):
        self.file = self.client.open(self.path, self.mode)
        self.zip = ZipFile(self.file, self.mode)
        index = self.zip.namelist()
        if self.fname is None and len(index) == 1:
            self.fname = index[0]
        if self.fname not in index:
            msg = "File %s not found in zip %s" % (self.fname, self.path)
            raise FileNotFoundError(msg)
        self.innerzip = self.zip.open(self.fname, self.mode)
        return self.innerzip

    def __exit__(self, *args):
        self.innerzip.close()
        self.zip.close()
        self.file.close()
