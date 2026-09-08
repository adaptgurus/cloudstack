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
  buildSelfServiceListParams,
  buildSelfServiceRouteQuery,
  countResponse
} from '@/views/dashboard/selfServiceDashboard'

describe('LayerSentry self-service dashboard helpers', () => {
  it('scopes list queries to the active project without changing account sessions', () => {
    expect(buildSelfServiceListParams({ id: 'project-1' }, { hypervisor: 'KVM' })).toEqual({
      listall: true,
      page: 1,
      pagesize: 1,
      hypervisor: 'KVM',
      projectid: 'project-1'
    })
    expect(buildSelfServiceListParams(null, { state: 'Running' })).toEqual({
      listall: true,
      page: 1,
      pagesize: 1,
      state: 'Running'
    })
  })

  it('builds deep-link queries with the same project scope', () => {
    expect(buildSelfServiceRouteQuery({ id: 'project-1' }, { hypervisor: 'KVM' })).toEqual({
      hypervisor: 'KVM',
      projectid: 'project-1'
    })
    expect(buildSelfServiceRouteQuery(undefined, { state: 'Running' })).toEqual({ state: 'Running' })
  })

  it('reads count-only and list-shaped API responses safely', () => {
    expect(countResponse({ listvolumesresponse: { count: 4 } }, 'listvolumesresponse', 'volume')).toBe(4)
    expect(countResponse({ listvolumesresponse: { volume: [{}, {}] } }, 'listvolumesresponse', 'volume')).toBe(2)
    expect(countResponse(undefined, 'listvolumesresponse', 'volume')).toBe(0)
  })
})
