// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

import { getDashboardQuickActions, getDashboardRole } from '@/views/dashboard/dashboardRole'

describe('LayerSentry dashboard roles', () => {
  it('prioritizes an active project scope', () => {
    expect(getDashboardRole({ roletype: 'DomainAdmin' }, {}, true)).toBe('project')
  })

  it('maps CloudStack domain administrators to department administrators', () => {
    expect(getDashboardRole({ roletype: 'DomainAdmin' }, { createVolume: {} })).toBe('department-admin')
  })

  it('uses granted mutation APIs to distinguish user and read-only sessions', () => {
    expect(getDashboardRole({ roletype: 'User' }, { deployVirtualMachine: {} })).toBe('user')
    expect(getDashboardRole({ roletype: 'User' }, { listVirtualMachines: {} })).toBe('read-only')
    expect(getDashboardRole({ roletype: 'DomainAdmin' }, { listAccounts: {} })).toBe('read-only')
  })

  it('returns only quick actions backed by granted APIs', () => {
    expect(getDashboardQuickActions({
      deployVirtualMachine: {},
      createBucket: {}
    })).toEqual([
      { key: 'instance', label: 'label.layersentry.quick.provision', path: '/quick-provision' }
    ])
  })

  it('returns no quick actions for a read-only API set', () => {
    expect(getDashboardQuickActions({ listVirtualMachines: {} })).toEqual([])
    expect(getDashboardQuickActions()).toEqual([])
  })
})
