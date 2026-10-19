// Thin JSON client for the local dashboard API. Mutations always send
// application/json (the server rejects anything else as a CSRF guard).
import {cleanParams} from './lib.js';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, {method = 'GET', body, params, signal, timeout = 30000} = {}) {
  let url = path;
  if (params) {
    const query = new URLSearchParams(cleanParams(params)).toString();
    if (query) url += `?${query}`;
  }
  const controller = new AbortController();
  const cancel = () => controller.abort(signal?.reason);
  if (signal?.aborted) cancel();
  else signal?.addEventListener('abort', cancel, {once: true});
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
  const init = {method, signal: controller.signal, headers: {Accept: 'application/json'}};
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  try {
    const res = await fetch(url, init);
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = {error: text}; }
    if (!res.ok) throw new ApiError(data.error || res.statusText || 'Request failed', res.status);
    return data;
  } catch (err) {
    if (timedOut) throw new ApiError('This request is taking too long. Collection continues in the background; retry this tab or open another.', 0);
    if (err.name === 'AbortError') throw err;
    if (err instanceof ApiError) throw err;
    throw new ApiError('Foothold is not reachable. If you stopped it, open it again from the Start menu, then retry.', 0);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

export const get = (path, params, signal) => api(path, {params, signal});
export const post = (path, body) => api(path, {method: 'POST', body});
export const put = (path, body) => api(path, {method: 'PUT', body});
export const patch = (path, body) => api(path, {method: 'PATCH', body});
export const del = (path) => api(path, {method: 'DELETE'});

export const enc = encodeURIComponent;

// In Foothold's own window (the browser's app mode, opened with ?app) another site's page opens in the
// user's browser, where their sign-ins are, not in a bare window of the app's profile.
export const appWindow = new URLSearchParams(globalThis.location?.search || '').has('app');
export function openExternal(url) {
  const tab = () => window.open(url, '_blank', 'noopener,noreferrer');
  if (appWindow) post('/api/open', {url}).catch(tab); else tab();
}

// POST JSON and save the file the server sends back (e.g. a merged PDF).
export async function download(path, body, fallbackName = 'download.pdf') {
  let res;
  try {
    res = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  } catch {
    throw new ApiError('Foothold is not reachable. If you stopped it, open it again from the Start menu, then retry.', 0);
  }
  if (!res.ok) {
    let message = res.statusText || 'Request failed';
    try { message = (await res.json()).error || message; } catch { /* not JSON */ }
    throw new ApiError(message, res.status);
  }
  const match = /filename\*=UTF-8''([^;]+)/.exec(res.headers.get('Content-Disposition') || '');
  const name = match ? decodeURIComponent(match[1]) : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), {href: url, download: name});
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return name;
}

// File → base64 (without the data: prefix) for JSON uploads.
export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = () => reject(new ApiError(`Could not read ${file.name}`, 0));
    reader.readAsDataURL(file);
  });
}
