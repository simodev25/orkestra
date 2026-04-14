import { describe, it, expect, vi, afterEach } from 'vitest';
import { request, ApiError } from '../api-client';

function mockFetch(status: number, body: unknown, ok = status < 400) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
  });
}

describe('ApiError', () => {
  it('should have name ApiError', () => {
    const err = new ApiError(404, 'Not found');
    expect(err.name).toBe('ApiError');
  });

  it('should expose status and message', () => {
    const err = new ApiError(422, 'Validation error');
    expect(err.status).toBe(422);
    expect(err.message).toBe('Validation error');
  });

  it('should be instanceof Error', () => {
    const err = new ApiError(500, 'Server error');
    expect(err).toBeInstanceOf(Error);
  });
});

describe('request()', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('returns parsed JSON on 200', async () => {
    global.fetch = mockFetch(200, { id: 'abc', name: 'Test' });
    const result = await request<{ id: string; name: string }>('/api/agents');
    expect(result).toEqual({ id: 'abc', name: 'Test' });
  });

  it('returns undefined on 204', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error('No body')),
    });
    const result = await request('/api/agents/test');
    expect(result).toBeUndefined();
  });

  it('throws ApiError with string detail on 404', async () => {
    global.fetch = mockFetch(404, { detail: 'Agent not found' }, false);
    await expect(request('/api/agents/nonexistent')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'Agent not found',
    });
  });

  it('throws ApiError with joined message on validation error (array detail)', async () => {
    global.fetch = mockFetch(422, {
      detail: [
        { msg: 'field required', loc: ['body', 'name'] },
        { msg: 'too short', loc: ['body', 'id'] },
      ],
    }, false);
    const err = await request('/api/agents').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toContain('field required');
    expect(err.message).toContain('too short');
  });

  it('falls back to statusText when body has no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({}),
    });
    const err = await request('/api/crash').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe('Internal Server Error');
  });

  it('sends Content-Type application/json', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/test');
    const [, opts] = mockFn.mock.calls[0];
    expect((opts as any).headers['Content-Type']).toBe('application/json');
  });

  it('merges custom headers', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/test', { headers: { 'X-Custom': 'value' } });
    const [, opts] = mockFn.mock.calls[0];
    const headers = (opts as any).headers;
    expect(headers['X-Custom']).toBe('value');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('sends absolute URL as-is', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('https://external.api.com/resource');
    const [url] = mockFn.mock.calls[0];
    expect(url).toBe('https://external.api.com/resource');
  });

  it('prepends API_BASE to relative paths', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/families');
    const [url] = mockFn.mock.calls[0];
    expect(url).toContain('/api/families');
  });
});
