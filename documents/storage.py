"""
Custom S3 storage backend for documents in the RAG platform.
"""

from storages.backends.s3 import S3Storage

class DocumentS3Storage(S3Storage):
    """
    Storage class for user-uploaded documents.
    - default_acl = None : Enforces AWS modern 'Bucket owner enforced'(no public ACLs)
    - file_overwrite = False : Appends random string if a file with the same name exists.
    - querystring_auth = True : Generates secure, time-limited presigned URLS.
    """

    default_acl = None 
    file_overwrite = False 
    querystring_auth = True 