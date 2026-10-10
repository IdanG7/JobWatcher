// Thin JSON client for the local dashboard API. Mutations always send
// application/json (the server rejects anything else as a CSRF guard).
import {cleanParams} from './lib.js';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, {method = 'GET', body, params, signal} = {}) {
  let url = path;
  if (params) {
    const query = new URLSearchParams(cleanParams(params)).toString();
    if (query) url += `?${query}`;
  }
  const init = {method, signal, headers: {Accept: 'application/json'}};
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError('Dashboard server is not reachable. Is `python watcher.py --serve` running?', 0);
  }
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = {error: text}; }
  if (!res.ok) throw new ApiError(data.error || res.statusText || 'Request failed', res.status);
  return data;
}

export const get = (path, params, signal) => api(path, {params, signal});
export const post = (path, body) => api(path, {method: 'POST', body});
export const put = (path, body) => api(path, {method: 'PUT', body});
export const patch = (path, body) => api(path, {method: 'PATCH', body});
export const del = (path) => api(path, {method: 'DELETE'});

export const enc = encodeURIComponent;
