// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
// http://www.apache.org/licenses/LICENSE-2.0

import { shallowMount, flushPromises } from '@vue/test-utils'
import Page from '@/views/layersentry/KubernetesDataServices.vue'
import { kubernetesRequest } from '@/api/layersentryKubernetes'

jest.mock('@/api', () => ({ getAPI: jest.fn() }))
jest.mock('@/api/layersentryKubernetes', () => ({
  ...jest.requireActual('@/api/layersentryKubernetes'),
  kubernetesRequest: jest.fn(),
  discoverKubernetesResources: jest.fn(async (api, command) => command === 'listProjects' ? [{ id: 'project-one', state: 'Active', name: 'Team' }] : [])
}))

let wrapper
const mountPage = () => shallowMount(Page, {
  global: {
    mocks: { $store: { getters: { userInfo: { id: 'user' } } } },
    stubs: Object.fromEntries(['page-header', 'alert', 'space', 'select', 'select-option', 'button', 'tabs', 'tab-pane', 'row', 'col', 'card', 'form', 'form-item', 'input', 'divider', 'input-number', 'empty', 'list', 'list-item', 'tag', 'table'].map(name => ['a-' + name, true]))
  }
})

beforeEach(async () => {
  jest.useFakeTimers()
  kubernetesRequest.mockImplementation(async path => path === '/readiness'
    ? { kubernetes: false, gates: {} }
    : path.startsWith('/operations') ? { operations: [], nextCursor: null } : { clusters: [] })
  wrapper = mountPage()
  await flushPromises()
  kubernetesRequest.mockReset()
})
afterEach(() => { wrapper.unmount(); jest.useRealTimers() })

it('does not enable provisioning from browser configuration flags', () => {
  expect(wrapper.vm.serverReady).toBe(false)
  wrapper.vm.readiness = { kubernetes: true, gates: { capc_volume_ownership_safe: false } }
  expect(wrapper.vm.serverReady).toBe(false)
})

it('rejects stale project runtime responses after scope reset', async () => {
  let resolveHistory
  kubernetesRequest.mockImplementation(path => path.startsWith('/operations')
    ? new Promise(resolve => { resolveHistory = resolve })
    : Promise.resolve({ clusters: [{ name: 'old-tenant' }] }))
  const pending = wrapper.vm.loadRuntime(wrapper.vm.generation)
  wrapper.vm.resetScope()
  resolveHistory({ operations: [{ id: 'old' }], nextCursor: null })
  await pending
  expect(wrapper.vm.operations).toEqual([])
  expect(wrapper.vm.clusters).toEqual([])
})

it('serializes a double-click and retains accepted status without asserting readiness', async () => {
  let resolveMutation
  const attempt = { path: '/clusters', method: 'POST', body: { project_id: wrapper.vm.projectId }, idempotencyKey: 'a'.repeat(32) }
  kubernetesRequest.mockImplementation(() => new Promise(resolve => { resolveMutation = resolve }))
  const first = wrapper.vm.submitAttempt(attempt)
  await wrapper.vm.submitAttempt(attempt)
  expect(kubernetesRequest).toHaveBeenCalledTimes(1)
  resolveMutation({ operation: { id: 'op1', projectId: wrapper.vm.projectId, status: 'REQUESTED' } })
  await first
  expect(wrapper.vm.operations[0].status).toBe('REQUESTED')
  expect(wrapper.vm.clusters).toEqual([])
  expect(wrapper.vm.notice).toContain('acceptance does not mean')
})

it('keeps an ambiguous mutation locked to its exact original request', async () => {
  const attempt = { path: '/clusters', method: 'POST', body: { project_id: wrapper.vm.projectId }, idempotencyKey: 'b'.repeat(32) }
  kubernetesRequest.mockRejectedValue(Object.assign(new Error('unknown outcome'), { ambiguous: true }))
  await wrapper.vm.submitAttempt(attempt)
  expect(wrapper.vm.uncertainAttempt).toEqual(attempt)
  expect(wrapper.vm.requestLocked).toBe(true)
})

it('stops bounded polling without resubmitting an operation', () => {
  wrapper.vm.operations = [{ id: 'op1', status: 'RUNNING' }]
  wrapper.vm.pollCount = 120
  wrapper.vm.schedulePoll()
  expect(wrapper.vm.pollingPaused).toBe(true)
  expect(kubernetesRequest).not.toHaveBeenCalled()
})

it('requires exact deletion confirmation and qualified server readiness', () => {
  wrapper.vm.selectedCluster = { name: 'team', namespace: 'managed' }
  wrapper.vm.deleteConfirmation = 'different'
  wrapper.vm.readiness = { kubernetes: true, gates: { capc_volume_ownership_safe: true } }
  expect(wrapper.vm.canDelete).toBe(false)
  wrapper.vm.deleteConfirmation = 'team'
  expect(wrapper.vm.canDelete).toBe(true)
})

it('discards an older same-project inventory refresh that finishes last', async () => {
  let releaseOld
  kubernetesRequest
    .mockImplementationOnce(() => new Promise(resolve => { releaseOld = resolve }))
    .mockResolvedValueOnce({ clusters: [{ name: 'stale' }] })
    .mockResolvedValueOnce({ operations: [{ id: 'new' }], nextCursor: null })
    .mockResolvedValueOnce({ clusters: [{ name: 'fresh' }] })
  const old = wrapper.vm.loadRuntime(wrapper.vm.generation)
  await wrapper.vm.loadRuntime(wrapper.vm.generation)
  releaseOld({ operations: [{ id: 'old' }], nextCursor: null })
  await old
  expect(wrapper.vm.operations).toEqual([{ id: 'new' }])
  expect(wrapper.vm.clusters).toEqual([{ name: 'fresh' }])
})

it('clears readiness if polling loses authorization', async () => {
  wrapper.vm.readiness = { kubernetes: true, gates: { capc_volume_ownership_safe: true } }
  wrapper.vm.operations = [{ status: 'RUNNING' }]
  kubernetesRequest.mockRejectedValue(Object.assign(new Error('No access'), { status: 403 }))
  wrapper.vm.schedulePoll()
  jest.advanceTimersByTime(5000)
  await flushPromises()
  expect(wrapper.vm.serverReady).toBe(false)
  expect(wrapper.vm.pollingPaused).toBe(true)
})

it('discovers only server-qualified images for the current project and Site', async () => {
  const image = { id: 'qualified', name: 'RKE2', isready: true, hypervisor: 'KVM' }
  kubernetesRequest.mockResolvedValue({ images: [image] })
  wrapper.vm.draft.zone_id = 'site-one'
  await wrapper.vm.loadSiteDiscovery()
  expect(kubernetesRequest).toHaveBeenCalledWith('/images?projectId=project-one&zoneId=site-one', expect.any(Object))
  expect(wrapper.vm.images).toEqual([image])
})
