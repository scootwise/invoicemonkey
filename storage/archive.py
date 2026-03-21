"""PDF Archive Storage - R2/S3 with encryption"""
import boto3
import hashlib
from datetime import datetime, timedelta
from config.settings import (
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_URL
)


class PDFArchive:
    """Store and retrieve encrypted PDFs from R2/S3"""
    
    def __init__(self):
        self.s3 = None
        self.bucket = R2_BUCKET_NAME
        self._init_client()
    
    def _init_client(self):
        """Initialize S3-compatible client for R2"""
        if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
            # Fallback to local storage for dev
            self.local_mode = True
            return
        
        self.local_mode = False
        endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name='auto'
        )
    
    def store_pdf(self, user_id: str, invoice_id: str, pdf_bytes: bytes, filename: str) -> dict:
        """Store PDF in archive, return storage reference"""
        
        # Generate unique key
        date_prefix = datetime.utcnow().strftime('%Y/%m')
        safe_filename = filename.replace(' ', '_')[:50]
        key = f"{user_id}/{date_prefix}/{invoice_id}_{safe_filename}"
        
        if self.local_mode:
            # Local storage fallback
            import os
            local_path = f"./archive/{key}"
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(pdf_bytes)
            
            return {
                'key': key,
                'size': len(pdf_bytes),
                'storage_type': 'local',
                'url': local_path
            }
        
        # Upload to R2 with encryption
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=pdf_bytes,
            ContentType='application/pdf',
            ServerSideEncryption='AES256',
            Metadata={
                'user_id': user_id,
                'invoice_id': invoice_id,
                'original_filename': filename,
                'uploaded_at': datetime.utcnow().isoformat()
            }
        )
        
        # Generate presigned URL (expires in 15 min)
        url = self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=900  # 15 minutes
        )
        
        return {
            'key': key,
            'size': len(pdf_bytes),
            'storage_type': 'r2',
            'url': url,
            'expires_at': (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }
    
    def get_download_url(self, key: str, expires_in: int = 900) -> str:
        """Generate fresh presigned URL for download"""
        if self.local_mode:
            return f"file://./archive/{key}"
        
        url = self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expires_in
        )
        return url
    
    def delete_pdf(self, key: str) -> bool:
        """Delete PDF from archive"""
        if self.local_mode:
            import os
            try:
                os.remove(f"./archive/{key}")
                return True
            except:
                return False
        
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False
    
    def list_user_pdfs(self, user_id: str) -> list:
        """List all PDFs for a user"""
        if self.local_mode:
            import os
            import glob
            
            pattern = f"./archive/{user_id}/**/*.pdf"
            files = glob.glob(pattern, recursive=True)
            
            results = []
            for f in files:
                rel_path = f.replace('./archive/', '')
                stat = os.stat(f)
                results.append({
                    'key': rel_path,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return results
        
        # List from R2
        prefix = f"{user_id}/"
        response = self.s3.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix
        )
        
        results = []
        for obj in response.get('Contents', []):
            results.append({
                'key': obj['Key'],
                'size': obj['Size'],
                'modified': obj['LastModified'].isoformat()
            })
        
        return results
