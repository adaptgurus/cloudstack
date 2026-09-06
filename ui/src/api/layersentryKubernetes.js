// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0

import Cookies from 'js-cookie'

const BASE = '/client/layersentry-k8s/v1/kubernetes'

export class KubernetesRequestError extends Error {
  constructor (message, { status = 0, ambiguous = false } = {}) {
    super(message)
    this.status = status
    this.ambiguous = ambiguous
  }
}

// This JSON boundary deliberately has no CloudStack request interceptors.
export async function kubernetesRequest (path, { method = 'GET', body, idempotencyKey, signal, timeout = 15000 } = {}) {
  if (!/^\/(readiness|clusters|operations|images)(\/[a-zA-Z0-9-]+)*(\?[^#]*)?$/.test(path)) throw new Error('Invalid Kubernetes API path')
  const sessionKey = Cookies.get('sessionkey')
  if (!sessionKey) throw new KubernetesRequestError('Sign in again to access Kubernetes services.', { status: 401 })
  const mutation = method !== 'GET'
  if (mutation && !/^[a-zA-Z0-9_-]{16,128}$/.test(idempotencyKey || '')) throw new Error('A mutation request identifier is required.')
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) controller.abort()
  if (signal) signal.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(abort, timeout)
  try {
    const response = await fetch(BASE + path, {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'error',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'X-LayerSentry-Session-Key': sessionKey,
        ...(mutation ? { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey } : {})
      },
      ...(mutation ? { body: JSON.stringify(body) } : {})
    })
    if (!(response.headers.get('content-type') || '').toLowerCase().includes('application/json')) {
      throw new KubernetesRequestError('Kubernetes service is unavailable or its portal connection is not configured.', { status: response.status, ambiguous: mutation })
    }
    const payload = await response.json()
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Invalid controller response')
    if (!response.ok) {
      const message = response.status === 401 ? 'Your session expired. Sign in again.'
        : response.status === 403 ? 'You do not have permission for this Kubernetes action.'
          : (typeof payload.error === 'string' ? payload.error.slice(0, 600) : 'Kubernetes service request failed.')
      throw new KubernetesRequestError(message, { status: response.status, ambiguous: mutation && response.status >= 500 })
    }
    return payload
  } catch (error) {
    if (error instanceof KubernetesRequestError) throw error
    throw new KubernetesRequestError(mutation
      ? 'Submission outcome is unknown. Check operation history before retrying this exact request.'
      : 'Kubernetes service could not be read. Check connectivity and refresh.', { ambiguous: mutation })
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', abort)
  }
}

export function mutationAttempt (method, path, body) {
  const bytes = new Uint8Array(24)
  window.crypto.getRandomValues(bytes)
  return Object.freeze({
    method,
    path,
    body: JSON.parse(JSON.stringify(body)),
    idempotencyKey: Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')
  })
}

export function scopeQuery (projectId, extra = {}) {
  return '?' + new URLSearchParams({ projectId, ...extra }).toString()
}

export const operationNeedsPolling = operation => ['REQUESTED', 'VALIDATING', 'RUNNING', 'DELETING', 'UNKNOWN', 'FAILED_RETRYABLE'].includes(operation.status)

// A bounded complete inventory prevents accidentally offering a silently truncated list.
export async function discoverKubernetesResources (getAPI, command, collection, args = {}, current = () => true) {
  const rows = new Map()
  for (let page = 1; page <= 50; page++) {
    if (!current()) return []
    const response = await getAPI(command, { ...args, page, pagesize: 100 })
    if (!current()) return []
    const envelope = response?.[command.toLowerCase() + 'response']
    if (!envelope || typeof envelope !== 'object') throw new Error('Cloud inventory response is invalid.')
    const items = envelope[collection] || []
    if (!Array.isArray(items)) throw new Error('Cloud inventory collection is invalid.')
    let added = 0
    for (const item of items) {
      if (!item?.id) throw new Error('Cloud inventory resource identifier is missing.')
      if (!rows.has(item.id)) added++
      rows.set(item.id, item)
    }
    if (items.length < 100 && (!Number.isFinite(envelope.count) || rows.size >= envelope.count)) return [...rows.values()]
    if (!added) throw new Error('Cloud inventory pagination did not advance. Refresh before provisioning.')
  }
  throw new Error('Cloud inventory exceeds the safe discovery limit. Narrow the project scope.')
}
