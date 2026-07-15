// Raw byte PUT to a signed upload URL (media presign / import flows).
//
// The URL is self-authorising (HMAC `?expires=&token=` for the MinIO proxy,
// or an AWS presigned URL) — deliberately NO cookies and NO CSRF header, same
// contract as a device upload (docs/device-protocol.md §3.3).
//
// Uses XMLHttpRequest rather than fetch so `onProgress` can report real
// upload-byte progress (fetch has no cross-browser-reliable upload progress
// event for a request body).
export async function putToUploadUrl(
  url: string,
  data: Blob | File,
  contentType?: string,
  onProgress?: (fraction: number) => void,
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    if (contentType) xhr.setRequestHeader("Content-Type", contentType);
    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(e.loaded / e.total);
      };
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Upload failed (network error)"));
    xhr.send(data);
  });
}
