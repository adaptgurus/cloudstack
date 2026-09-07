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

import {
  buildQuickProvisionDeployParams,
  normaliseAdditionalNetworks,
  quickProvisionBlockingIssues,
  validateQuickProvisionDataVolumes,
  validateQuickProvisionRootStorage
} from '@/views/layersentry/quickProvision'

const offerings = [
  { id: 'fixed', name: 'Fixed', iscustomized: false, iscustomizediops: false },
  { id: 'custom', name: 'Custom', iscustomized: true, iscustomizediops: false },
  { id: 'iops', name: 'IOPS', iscustomized: true, iscustomizediops: true }
]

describe('LayerSentry Quick Provision native CloudStack contract', () => {
  it('removes duplicate and primary-network entries from additional networks', () => {
    expect(normaliseAdditionalNetworks('net-a', ['net-a', 'net-b', 'net-b', 'net-c'])).toEqual(['net-b', 'net-c'])
  })

  it('validates customized root-storage requirements without inventing root IOPS fields', () => {
    expect(validateQuickProvisionRootStorage({
      rootdiskofferingid: 'custom'
    }, offerings)).toEqual([
      'The selected root Storage Profile requires a positive root disk size.'
    ])
    expect(validateQuickProvisionRootStorage({
      rootdiskofferingid: 'iops',
      rootdisksize: 80
    }, offerings)).toEqual([
      'Custom-IOPS root Storage Profiles require the advanced deployment workflow.'
    ])
  })

  it('validates customized size and IOPS requirements before mutation', () => {
    expect(validateQuickProvisionDataVolumes([
      { diskofferingid: 'fixed' },
      { diskofferingid: 'custom' },
      { diskofferingid: 'iops', size: 20, miniops: 200, maxiops: 100 }
    ], offerings)).toEqual([
      'Data volume 2 requires a positive size.',
      'Data volume 3 requires maximum IOPS greater than or equal to minimum IOPS.'
    ])
  })

  it('builds native multiple-data-disk and multi-network deploy parameters', () => {
    expect(buildQuickProvisionDeployParams({
      form: {
        name: 'app-01',
        zoneid: 'zone-1',
        templateid: 'tmpl-1',
        serviceofferingid: 'compute-1',
        rootdiskofferingid: 'fixed',
        rootdisksize: 80,
        dataVolumes: [
          { diskofferingid: 'fixed' },
          { diskofferingid: 'custom', size: 50 },
          { diskofferingid: 'iops', size: 100, miniops: 500, maxiops: 1000 }
        ],
        networkid: 'net-a',
        additionalnetworkids: ['net-b', 'net-a', 'net-c'],
        ipaddress: '10.10.10.20',
        startvm: true
      },
      networkType: 'Advanced',
      storageProfiles: offerings,
      projectId: 'project-1'
    })).toEqual({
      name: 'app-01',
      displayname: 'app-01',
      zoneid: 'zone-1',
      templateid: 'tmpl-1',
      serviceofferingid: 'compute-1',
      hypervisor: 'KVM',
      startvm: true,
      projectid: 'project-1',
      overridediskofferingid: 'fixed',
      rootdisksize: 80,
      'datadisksdetails[0].diskofferingid': 'fixed',
      'datadisksdetails[0].deviceid': 1,
      'datadisksdetails[1].diskofferingid': 'custom',
      'datadisksdetails[1].deviceid': 2,
      'datadisksdetails[1].size': 50,
      'datadisksdetails[2].diskofferingid': 'iops',
      'datadisksdetails[2].deviceid': 3,
      'datadisksdetails[2].size': 100,
      'datadisksdetails[2].miniops': 500,
      'datadisksdetails[2].maxiops': 1000,
      'iptonetworklist[0].networkid': 'net-a',
      'iptonetworklist[0].ip': '10.10.10.20',
      'iptonetworklist[1].networkid': 'net-b',
      'iptonetworklist[2].networkid': 'net-c'
    })
  })

  it('does not invent explicit network parameters in a Basic Site', () => {
    const params = buildQuickProvisionDeployParams({
      form: {
        name: 'basic-01',
        zoneid: 'zone-basic',
        templateid: 'tmpl-1',
        serviceofferingid: 'compute-1',
        dataVolumes: [],
        networkid: 'ignored',
        additionalnetworkids: ['ignored-2'],
        startvm: false
      },
      networkType: 'Basic',
      storageProfiles: offerings
    })
    expect(Object.keys(params).some(key => key.startsWith('iptonetworklist'))).toBe(false)
  })

  it('blocks submit until KVM and image preflight evidence is current', () => {
    const form = {
      name: 'app-01',
      zoneid: 'zone-1',
      templateid: 'tmpl-1',
      serviceofferingid: 'compute-1',
      networkid: 'net-a',
      dataVolumes: []
    }
    expect(quickProvisionBlockingIssues({
      form,
      networkType: 'Advanced',
      storageProfiles: offerings,
      computeProfiles: [{ id: 'compute-1', iscustomized: false }],
      kvmSiteReady: false,
      imageReady: false
    })).toEqual([
      'KVM availability for the Site is not verified.',
      'The selected OS Image has not passed the KVM preflight.'
    ])
    expect(quickProvisionBlockingIssues({
      form,
      networkType: 'Advanced',
      storageProfiles: offerings,
      computeProfiles: [{ id: 'compute-1', iscustomized: false }],
      kvmSiteReady: true,
      imageReady: true
    })).toEqual([])
  })
})
