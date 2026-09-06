// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied. See the License for the
// specific language governing permissions and limitations
// under the License.

import { checkKvmSite, checkKvmImage } from '@/config/kvmProvisioning'

jest.mock('@/vue-app', () => ({ vueProps: { $config: {} } }))

describe('KVM provisioning capability and image validation', () => {
  it('requires a selected Site before making a capability request', async () => {
    const api = jest.fn()
    await expect(checkKvmSite(api)).rejects.toThrow('select.site')
    expect(api).not.toHaveBeenCalled()
  })

  it('uses only KVM actually reported for the selected Site', async () => {
    const api = jest.fn().mockResolvedValue({ listhypervisorsresponse: { hypervisor: [{ name: 'VMware' }, { name: 'KVM' }] } })
    await expect(checkKvmSite(api, 'site-a')).resolves.toEqual([{ name: 'KVM' }])
    expect(api).toHaveBeenCalledWith('listHypervisors', { zoneid: 'site-a' })
  })

  it.each([{}, { count: 0 }, { hypervisor: [] }, { hypervisor: [{ name: 'VMware' }] }])('reports no KVM for %j', async body => {
    await expect(checkKvmSite(() => Promise.resolve({ listhypervisorsresponse: body }), 'site-a')).rejects.toThrow('unavailable')
  })

  it('distinguishes a failed/malformed lookup from a Site without KVM', async () => {
    await expect(checkKvmSite(() => Promise.reject(new Error('denied')), 'site-a')).rejects.toThrow('lookup.failed')
    await expect(checkKvmSite(() => Promise.resolve({}), 'site-a')).rejects.toThrow('lookup.failed')
  })

  it('re-reads a ready KVM template by ID and Site using native fields', async () => {
    const api = jest.fn().mockResolvedValue({ listtemplatesresponse: { template: [{ id: 'image-a', hypervisor: 'KVM', isready: true }] } })
    await checkKvmImage(api, 'site-a', 'templateid', 'image-a', { projectid: 'project-a' })
    expect(api).toHaveBeenCalledWith('listTemplates', {
      zoneid: 'site-a', id: 'image-a', projectid: 'project-a', hypervisor: 'KVM', isready: true, templatefilter: 'executable'
    })
  })

  it.each([
    { id: 'image-a', hypervisor: 'VMware', isready: true },
    { id: 'image-a', hypervisor: 'KVM', isready: false },
    { id: 'image-a', isready: true },
    { id: 'other-image', hypervisor: 'KVM', isready: true }
  ])('rejects incompatible, unready, unknown and replaced images: %j', async image => {
    const api = () => Promise.resolve({ listtemplatesresponse: { template: [image] } })
    await expect(checkKvmImage(api, 'site-a', 'templateid', 'image-a')).rejects.toThrow('image.invalid')
  })

  it('requires the native CKS template marker when requested', async () => {
    const api = jest.fn().mockResolvedValue({ listtemplatesresponse: { template: [{ id: 'image-a', hypervisor: 'KVM', isready: true }] } })
    await expect(checkKvmImage(api, 'site-a', 'templateid', 'image-a', { forcks: true })).rejects.toThrow('image.invalid')
  })

  it('accepts a neutral ready bootable ISO without filtering it out at the server', async () => {
    const api = jest.fn().mockResolvedValue({ listisosresponse: { iso: [{ id: 'iso-a', hypervisor: 'None', isready: true, bootable: true }] } })
    await checkKvmImage(api, 'site-a', 'isoid', 'iso-a')
    expect(api.mock.calls[0][1]).not.toHaveProperty('hypervisor')
  })

  it('fails closed on image API errors and removed images', async () => {
    await expect(checkKvmImage(() => Promise.reject(new Error('denied')), 'site-a', 'templateid', 'image-a')).rejects.toThrow('image.lookup.failed')
    await expect(checkKvmImage(() => Promise.resolve({ listtemplatesresponse: {} }), 'site-a', 'templateid', 'image-a')).rejects.toThrow('image.invalid')
  })

  it('resolves snapshot hypervisor from the readable source volume', async () => {
    const api = jest.fn()
      .mockResolvedValueOnce({ listsnapshotsresponse: { snapshot: [{ id: 'snapshot-a', volumeid: 'volume-a', volumetype: 'ROOT' }] } })
      .mockResolvedValueOnce({ listvolumesresponse: { volume: [{ id: 'volume-a', hypervisor: 'KVM' }] } })
    await checkKvmImage(api, 'site-a', 'snapshotid', 'snapshot-a')
    expect(api.mock.calls[1]).toEqual(['listVolumes', { zoneid: 'site-a', id: 'volume-a' }])
  })

  it('rejects a non-KVM volume and a snapshot whose source volume is unavailable', async () => {
    await expect(checkKvmImage(() => Promise.resolve({ listvolumesresponse: { volume: [{ id: 'volume-a', hypervisor: 'VMware' }] } }), 'site-a', 'volumeid', 'volume-a')).rejects.toThrow('image.invalid')
    const api = jest.fn()
      .mockResolvedValueOnce({ listsnapshotsresponse: { snapshot: [{ id: 'snapshot-a', volumeid: 'volume-a', volumetype: 'ROOT' }] } })
      .mockResolvedValueOnce({ listvolumesresponse: {} })
    await expect(checkKvmImage(api, 'site-a', 'snapshotid', 'snapshot-a')).rejects.toThrow('image.invalid')
  })
})
