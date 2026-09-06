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

const packageRow = (extra = {}) => ({ package: 'example-operator', version: '1.2.3', profile: 'standard', catalogSha256: 'a'.repeat(64), available: true, stateful: false, blockers: [], ...extra })
const pendingPackage = { status: 'PENDING', detail: 'Package is absent or not yet Ready.', resources: {} }
const unknownOperation = projectId => ({ id: '12345678-1234-1234-1234-123456789abc', projectId, targetName: 'team', kind: 'kubernetes.package.install', status: 'UNKNOWN' })
const choosePackage = async (row = packageRow()) => {
  kubernetesRequest.mockResolvedValue(pendingPackage)
  wrapper.vm.readiness = { kubernetes: true, gates: { capc_volume_ownership_safe: true } }
  wrapper.vm.selectedCluster = { name: 'team', namespace: 'tenant-a', ready: true }
  wrapper.vm.packageCatalog = [row]
  wrapper.vm.packageSelection = wrapper.vm.packageKey(row)
  await flushPromises()
  kubernetesRequest.mockReset()
}
Object.defineProperty(window, 'crypto', { value: require('crypto').webcrypto, configurable: true })

it('discovers approved profiles without converting availability into installed readiness', async () => {
  const row = packageRow()
  kubernetesRequest.mockResolvedValue({ packages: [row] })
  await wrapper.vm.loadPackageCatalog()
  expect(kubernetesRequest).toHaveBeenCalledWith('/packages?projectId=project-one', expect.any(Object))
  expect(wrapper.vm.packageCatalog).toEqual([row])
  expect(wrapper.vm.packageStatus).toBeNull()
  expect(wrapper.vm.canInstallPackage).toBe(false)
})

it('fences catalog results from a previous project and malformed catalog values', async () => {
  let resolveCatalog
  kubernetesRequest.mockImplementation(() => new Promise(resolve => { resolveCatalog = resolve }))
  const pending = wrapper.vm.loadPackageCatalog()
  wrapper.vm.resetScope()
  resolveCatalog({ packages: [packageRow()] })
  await pending
  expect(wrapper.vm.packageCatalog).toEqual([])
  kubernetesRequest.mockResolvedValue({ packages: [packageRow({ catalogSha256: 'untrusted' })] })
  await wrapper.vm.loadPackageCatalog()
  expect(wrapper.vm.packageCatalog).toEqual([])
  expect(wrapper.vm.packageError).toContain('invalid')
})

it('fences status from an old profile and retains exact catalog selection', async () => {
  await choosePackage()
  let resolveOld
  kubernetesRequest.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
  const old = wrapper.vm.loadPackageStatus()
  const next = packageRow({ profile: 'other', catalogSha256: 'b'.repeat(64) })
  wrapper.vm.packageCatalog.push(next)
  kubernetesRequest.mockResolvedValue(pendingPackage)
  wrapper.vm.packageSelection = wrapper.vm.packageKey(next)
  await flushPromises()
  resolveOld({ status: 'CONVERGED', detail: 'Old profile ready', resources: {} })
  await old
  expect(wrapper.vm.packageStatus).toEqual(pendingPackage)
  expect(kubernetesRequest.mock.calls[1][0]).toContain('catalogSha256=' + 'b'.repeat(64))
})

it('fences old package status when cluster selection changes', async () => {
  await choosePackage()
  let resolveOld
  kubernetesRequest.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
  const old = wrapper.vm.loadPackageStatus()
  kubernetesRequest.mockResolvedValue({ cluster: { name: 'other', namespace: 'tenant-a', ready: true } })
  await wrapper.vm.selectCluster({ name: 'other', namespace: 'tenant-a' })
  resolveOld({ status: 'CONVERGED', detail: 'Wrong cluster result', resources: {} })
  await old
  expect(wrapper.vm.selectedCluster.name).toBe('other')
  expect(wrapper.vm.packageStatus).toBeNull()
})

it('submits only the selected profile with exact digest and recovers the original ambiguous request', async () => {
  await choosePackage()
  kubernetesRequest.mockRejectedValue(Object.assign(new Error('unknown outcome'), { ambiguous: true }))
  await wrapper.vm.installPackage()
  const attempt = wrapper.vm.uncertainAttempt
  expect(attempt.body).toEqual({ clusterName: 'team', namespace: 'tenant-a', projectId: 'project-one', package: 'example-operator', version: '1.2.3', profile: 'standard', catalogSha256: 'a'.repeat(64) })
  expect(attempt.path).toBe('/clusters/team/packages')
  expect(wrapper.vm.requestLocked).toBe(true)
  kubernetesRequest.mockImplementation(async (path, options) => options.method === 'POST'
    ? { operation: { id: 'package-op', projectId: 'project-one', targetName: 'team', kind: 'kubernetes.package.install', status: 'REQUESTED' } } : pendingPackage)
  await wrapper.vm.submitAttempt(attempt)
  expect(kubernetesRequest.mock.calls[1][1].idempotencyKey).toBe(attempt.idempotencyKey)
  expect(wrapper.vm.operations[0].status).toBe('REQUESTED')
  expect(wrapper.vm.packageStatus?.status).not.toBe('CONVERGED')
})

it('blocks historical install and stateful uninstall while requiring exact stateless confirmation', async () => {
  await choosePackage(packageRow({ available: false, blockers: ['Historical profile'] }))
  expect(wrapper.vm.canInstallPackage).toBe(false)
  wrapper.vm.packageDeleteConfirmation = 'other'
  expect(wrapper.vm.canUninstallPackage).toBe(false)
  wrapper.vm.packageDeleteConfirmation = 'example-operator'
  expect(wrapper.vm.canUninstallPackage).toBe(true)
  wrapper.vm.packageCatalog[0].stateful = true
  expect(wrapper.vm.canUninstallPackage).toBe(false)
  wrapper.vm.packageCatalog[0].stateful = false
  kubernetesRequest.mockResolvedValue({ operation: { id: 'delete-op', projectId: 'project-one', targetName: 'team', kind: 'kubernetes.package.delete', status: 'REQUESTED' } })
  await wrapper.vm.uninstallPackage()
  expect(kubernetesRequest.mock.calls[0][1]).toMatchObject({ method: 'DELETE', body: { catalogSha256: 'a'.repeat(64), projectId: 'project-one' } })
})

it('requires fresh package state, ready target and no active cluster reservation', async () => {
  await choosePackage()
  expect(wrapper.vm.canInstallPackage).toBe(true)
  wrapper.vm.packageStatus = null
  expect(wrapper.vm.canInstallPackage).toBe(false)
  wrapper.vm.packageStatus = pendingPackage
  wrapper.vm.selectedCluster.ready = false
  expect(wrapper.vm.canInstallPackage).toBe(false)
  wrapper.vm.selectedCluster.ready = true
  wrapper.vm.operations = [unknownOperation('project-one')]
  expect(wrapper.vm.canInstallPackage).toBe(false)
})

it('observes only an UNKNOWN operation in the current project with an empty body', async () => {
  const operation = unknownOperation('project-one')
  wrapper.vm.operations = [operation]
  kubernetesRequest.mockResolvedValue({ operation: { ...operation, status: 'RUNNING' } })
  await wrapper.vm.observeOperation({ ...operation, projectId: 'other' })
  expect(kubernetesRequest).not.toHaveBeenCalled()
  await wrapper.vm.observeOperation(operation)
  expect(kubernetesRequest).toHaveBeenCalledWith('/operations/' + operation.id + '/reconcile', expect.objectContaining({ method: 'POST', body: {} }))
  expect(wrapper.vm.operations[0].status).toBe('RUNNING')
  expect(wrapper.vm.uncertainAttempt).toBeNull()
})

it('requires fresh history after ambiguous observation and never replays it automatically', async () => {
  const operation = unknownOperation('project-one')
  wrapper.vm.operations = [operation]
  kubernetesRequest.mockRejectedValue(Object.assign(new Error('unknown'), { ambiguous: true }))
  await wrapper.vm.observeOperation(operation)
  await wrapper.vm.observeOperation(operation)
  expect(kubernetesRequest).toHaveBeenCalledTimes(1)
  expect(wrapper.vm.uncertainObservationId).toBe(operation.id)
  expect(wrapper.vm.uncertainAttempt).toBeNull()
  kubernetesRequest.mockImplementation(async path => path.startsWith('/operations') ? { operations: [operation] } : { clusters: [] })
  await wrapper.vm.loadRuntime(wrapper.vm.generation)
  expect(wrapper.vm.uncertainObservationId).toBeNull()
})

it('preserves observation authorization failures and rejects stale operation receipts', async () => {
  const operation = unknownOperation('project-one')
  wrapper.vm.operations = [operation]
  kubernetesRequest.mockRejectedValue(Object.assign(new Error('No access'), { status: 403 }))
  await wrapper.vm.observeOperation(operation)
  expect(wrapper.vm.error).toBe('No access')
  expect(wrapper.vm.operations[0].status).toBe('UNKNOWN')
  let resolveObservation
  kubernetesRequest.mockImplementation(() => new Promise(resolve => { resolveObservation = resolve }))
  const pending = wrapper.vm.observeOperation(operation)
  wrapper.vm.resetScope()
  resolveObservation({ operation: { ...operation, status: 'RUNNING' } })
  await pending
  expect(wrapper.vm.operations).toEqual([])
})

it('does not let a history read started before observation overwrite its new receipt', async () => {
  const operation = unknownOperation('project-one')
  wrapper.vm.operations = [operation]
  let resolveHistory
  kubernetesRequest.mockImplementationOnce(() => new Promise(resolve => { resolveHistory = resolve }))
    .mockResolvedValueOnce({ clusters: [] })
  const pending = wrapper.vm.loadRuntime(wrapper.vm.generation)
  kubernetesRequest.mockResolvedValue({ operation: { ...operation, status: 'RUNNING' } })
  await wrapper.vm.observeOperation(operation)
  resolveHistory({ operations: [operation] })
  await pending
  expect(wrapper.vm.operations[0].status).toBe('RUNNING')
})
