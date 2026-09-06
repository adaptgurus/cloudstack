// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
// http://www.apache.org/licenses/LICENSE-2.0

import Cookies from 'js-cookie'
import { kubernetesRequest, discoverKubernetesResources, operationNeedsPolling, mutationAttempt } from '@/api/layersentryKubernetes'

jest.mock('js-cookie', () => ({ get: jest.fn() }))
Object.defineProperty(window, 'crypto', { value: require('crypto').webcrypto, configurable: true })
const response = (body, status = 200, type = 'application/json') => ({ ok: status < 400, status, headers: { get: () => type }, json: async () => body })

beforeEach(() => {
  Cookies.get.mockReturnValue('runtime-session')
  global.fetch = jest.fn()
})
afterEach(() => { jest.useRealTimers(); delete global.fetch })

describe('Kubernetes JSON trust boundary', () => {
  it('uses only same-origin credentials and a session header, without native API query injection', async () => {
    fetch.mockResolvedValue(response({ kubernetes: false }))
    await kubernetesRequest('/readiness')
    expect(fetch).toHaveBeenCalledWith('/client/layersentry-k8s/v1/kubernetes/readiness', expect.objectContaining({
      credentials: 'same-origin', redirect: 'error', cache: 'no-store', headers: { Accept: 'application/json', 'X-LayerSentry-Session-Key': 'runtime-session' }
    }))
  })
  it('does not contact the service with a missing session', async () => {
    Cookies.get.mockReturnValue(undefined)
    await expect(kubernetesRequest('/readiness')).rejects.toMatchObject({ status: 401 })
    expect(fetch).not.toHaveBeenCalled()
  })
  it('rejects an unconfigured proxy returning an HTML login page', async () => {
    fetch.mockResolvedValue(response('<html>', 200, 'text/html'))
    await expect(kubernetesRequest('/readiness')).rejects.toThrow('portal connection is not configured')
  })
  it('preserves authorization failure rather than claiming an empty inventory', async () => {
    fetch.mockResolvedValue(response({ error: 'denied' }, 403))
    await expect(kubernetesRequest('/clusters?projectId=one')).rejects.toMatchObject({ status: 403, ambiguous: false })
  })
  it('retains the exact body and idempotency key for explicit retry after ambiguous transport failure', async () => {
    const draft = { project_id: 'one', name: 'team' }
    const attempt = mutationAttempt('POST', '/clusters', draft)
    draft.name = 'changed'
    fetch.mockRejectedValueOnce(new Error('connection lost')).mockResolvedValueOnce(response({ operation: { id: 'one' } }, 202))
    await expect(kubernetesRequest(attempt.path, attempt)).rejects.toMatchObject({ ambiguous: true })
    await kubernetesRequest(attempt.path, attempt)
    expect(fetch.mock.calls[0][1].headers['Idempotency-Key']).toBe(fetch.mock.calls[1][1].headers['Idempotency-Key'])
    expect(fetch.mock.calls[1][1].body).toBe(JSON.stringify({ project_id: 'one', name: 'team' }))
  })
  it('times out reads and does not retry automatically', async () => {
    jest.useFakeTimers()
    fetch.mockImplementation((url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted')))))
    const pending = kubernetesRequest('/readiness', { timeout: 50 })
    const assertion = expect(pending).rejects.toMatchObject({ ambiguous: false })
    jest.advanceTimersByTime(50)
    await assertion
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('rejects external and path traversal API targets', async () => {
    await expect(kubernetesRequest('https://example.com/readiness')).rejects.toThrow('Invalid Kubernetes API path')
    await expect(kubernetesRequest('/clusters/../readiness')).rejects.toThrow('Invalid Kubernetes API path')
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('CloudStack discovery and operation recovery', () => {
  it('pairs page with pagesize and preserves the exact project across every page', async () => {
    const read = jest.fn()
      .mockResolvedValueOnce({ listnetworksresponse: { count: 101, network: Array.from({ length: 100 }, (_, id) => ({ id: String(id) })) } })
      .mockResolvedValueOnce({ listnetworksresponse: { count: 101, network: [{ id: 'last' }] } })
    const resources = await discoverKubernetesResources(read, 'listNetworks', 'network', { projectid: 'one' })
    expect(resources).toHaveLength(101)
    expect(read.mock.calls.map(call => call[1])).toEqual([{ projectid: 'one', page: 1, pagesize: 100 }, { projectid: 'one', page: 2, pagesize: 100 }])
  })
  it('discards an in-flight response when caller scope changes', async () => {
    let current = true
    const read = jest.fn(async () => { current = false; return { listnetworksresponse: { network: [{ id: 'old-project' }] } } })
    expect(await discoverKubernetesResources(read, 'listNetworks', 'network', {}, () => current)).toEqual([])
  })
  it('rejects a pagination loop instead of silently truncating selectable resources', async () => {
    const read = jest.fn(async () => ({ listnetworksresponse: { count: 101, network: [{ id: 'same' }] } }))
    await expect(discoverKubernetesResources(read, 'listNetworks', 'network')).rejects.toThrow('did not advance')
    expect(read).toHaveBeenCalledTimes(2)
  })
  it('does not treat accepted or unknown operations as ready', () => {
    expect(operationNeedsPolling({ status: 'REQUESTED' })).toBe(true)
    expect(operationNeedsPolling({ status: 'UNKNOWN' })).toBe(true)
    expect(operationNeedsPolling({ status: 'READY' })).toBe(false)
  })
})
