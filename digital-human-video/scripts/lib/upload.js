const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { readJsonResponse } = require('./security');

async function getUploadPolicy(baseUrl, apiKey, model) {
  const url = `${baseUrl}/api/v1/uploads?action=getPolicy&model=${model}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' }
  });
  const data = await readJsonResponse(resp, 'Upload policy failed');
  if (!data.data?.upload_host) throw new Error('Invalid upload policy: missing upload_host');
  const uploadUrl = new URL(data.data.upload_host);
  if (uploadUrl.protocol !== 'https:') throw new Error('Upload policy returned a non-HTTPS host');
  return data.data;
}

async function uploadToDashScope(baseUrl, apiKey, filePath, originalName, model) {
  const policy = await getUploadPolicy(baseUrl, apiKey, model);
  const safeName = path.basename(originalName || filePath).replace(/[^a-zA-Z0-9._-]/g, '_');
  const objectKey = `${policy.upload_dir}/${crypto.randomUUID()}-${safeName}`;
  const bytes = fs.readFileSync(filePath);

  const form = new FormData();
  form.append('OSSAccessKeyId', policy.oss_access_key_id);
  form.append('Signature', policy.signature);
  form.append('policy', policy.policy);
  form.append('x-oss-object-acl', policy.x_oss_object_acl);
  form.append('x-oss-forbid-overwrite', policy.x_oss_forbid_overwrite);
  form.append('key', objectKey);
  form.append('success_action_status', '200');
  form.append('file', new Blob([bytes]), safeName);

  const resp = await fetch(policy.upload_host, { method: 'POST', body: form, redirect: 'error' });
  if (!resp.ok) throw new Error(`OSS upload failed: HTTP ${resp.status}`);
  return `oss://${objectKey}`;
}

module.exports = { uploadToDashScope };
